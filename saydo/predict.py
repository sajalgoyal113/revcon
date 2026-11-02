"""Predict P(promise kept) at the moment it is made — track-record + concall-context model.

The company's own past is combined with rich concall-level and promise-level signals:
- Symmetric point-in-time track record (category-group reliability `cat_kept_shrunk`,
  operational spread `ops_spread`, and ghosting behaviour `ghost_rate`).
- Concall & linguistic signals (prepared remarks vs Q&A, MD/CEO/Chairman attribution, hedging
  density, explicit conditions, reiteration/repeat persistence, range vs point specificity,
  period structure, horizon, and call promise density).
- Financial stretch vs trailing actuals (`ambition_gap` and `margin_gap`).
- Zero-shot LLM forecast log-odds (`muse_forecast_logit`).

Model Architecture:
- Calibrated Bayesian MAP Logistic Regression with domain-informed prior mean, shrunk intercept,
  and variance-floored standardization (preventing small-sample walk-forward variance explosion).
- Self-contained Pure-NumPy Gradient Boosted Decision Tree Classifier (`NumpyHistGBClassifier`)
  serialized directly into `model.json` (zero external `sklearn` requirement, full ensemble
  inference in `score_new` and `predict_guidance_accuracy`).

Validation:
  1. Leave-one-company-out (LOCO): can it judge a management team it has never seen?
  2. Walk-forward: train on outcomes public before a cutoff date, test on later promises.
"""
import json
import math
import re
from datetime import date, timedelta

import numpy as np

from . import financials, history, score

HEDGES = re.compile(r"\b(may|might|could|hopefully|hope|endeavou?r|subject to|depending|depends|"
                    r"expect|likely|should|try|trying|aspire|aspiration|ballpark|roughly|tentative|"
                    r"if (?:the|we|all)|god willing|fingers crossed)\b", re.I)
CONFIDENT = re.compile(r"\b(will|confident|committed|definitely|certainly|guidance|on track|assure)\b", re.I)
GROUPS = {
    "fin": {"revenue_growth", "revenue_target", "ebitda_margin", "pat_margin", "pat_growth", "ebitda_growth"},
    "build": {"capex", "capacity", "commissioning", "expansion"},
    "commercial": {"order_book", "order_inflow", "customer_win", "product_launch", "market_share"},
}

MODEL_HIST_FEATURES = [
    "cat_kept_shrunk", "ops_spread", "ghost_rate",
]
PROMISE_KEEP = [
    "grp_fin", "grp_build", "grp_commercial",
    "cat_high_base", "cat_low_base", "verifiable_fin",
    "pk_fy", "pk_q_date", "firm", "aspirational_or_hedged",
    "has_number", "dir_range_or_at_least", "reiteration", "has_conditions",
    "sec_prepared", "role_leader", "n_hedges",
    "horizon_yrs", "promises_in_call",
    "ambition_gap", "margin_gap", "muse_forecast_logit",
]
FEATURES = ["bias"] + MODEL_HIST_FEATURES + PROMISE_KEEP
L2 = 22.0
ENSEMBLE_TREE_WEIGHT = 0.15

PRIOR_W0 = {
    "cat_kept_shrunk": +0.25,
    "ops_spread": +0.10,
    "ghost_rate": -0.15,
    "ambition_gap": -0.22,
    "margin_gap": -0.22,
}


def _cat_grp(cat):
    for g, s in GROUPS.items():
        if cat in s:
            return g
    return "other"


class NumpyHistGBClassifier:
    """Self-contained Pure-NumPy Gradient Boosted Decision Trees on log-odds.
    Serializable to JSON so `model.json` is 100% portable without scikit-learn.
    """
    def __init__(self, n_estimators=30, learning_rate=0.06, min_samples_leaf=25, l2_leaf=15.0,
                 base_log_odds=0.0, trees=None):
        self.n_estimators = n_estimators
        self.lr = learning_rate
        self.min_leaf = min_samples_leaf
        self.l2 = l2_leaf
        self.base_log_odds = base_log_odds
        self.trees = trees if trees is not None else []

    def _fit_stump(self, X, grad, hess, w):
        _, d = X.shape
        best_gain = 0.0
        best_node = None
        G_tot = float((w * grad).sum())
        H_tot = float((w * hess).sum())
        base_score = (G_tot ** 2) / (H_tot + self.l2)
        for j in range(d):
            col = X[:, j]
            qs = np.unique(np.quantile(col, [0.15, 0.30, 0.50, 0.70, 0.85]))
            for thr in qs:
                left = col <= thr
                right = ~left
                if left.sum() < self.min_leaf or right.sum() < self.min_leaf:
                    continue
                G_L = float((w[left] * grad[left]).sum())
                H_L = float((w[left] * hess[left]).sum())
                G_R = G_tot - G_L
                H_R = H_tot - H_L
                gain = (G_L ** 2) / (H_L + self.l2) + (G_R ** 2) / (H_R + self.l2) - base_score
                if gain > best_gain:
                    best_gain = gain
                    best_node = {
                        "feat": int(j),
                        "thr": float(thr),
                        "left": float(-G_L / (H_L + self.l2)),
                        "right": float(-G_R / (H_R + self.l2)),
                    }
        return best_node

    def fit(self, X, y, sample_weight=None):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        w = np.ones(len(y)) if sample_weight is None else np.asarray(sample_weight, dtype=float)
        p0 = float(np.clip(((w * y).sum() + 30.0 * 0.43) / (w.sum() + 30.0), 0.10, 0.90))
        self.base_log_odds = math.log(p0 / (1.0 - p0))
        f = np.full(len(y), self.base_log_odds)
        self.trees = []
        for _ in range(self.n_estimators):
            p = 1.0 / (1.0 + np.exp(-np.clip(f, -20, 20)))
            grad = p - y
            hess = p * (1.0 - p)
            node = self._fit_stump(X, grad, hess, w)
            if node is None:
                break
            self.trees.append(node)
            mask = X[:, node["feat"]] <= node["thr"]
            f += self.lr * np.where(mask, node["left"], node["right"])
        return self

    def predict_proba(self, X):
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X[None, :]
        f = np.full(len(X), self.base_log_odds)
        for node in self.trees:
            if node["feat"] < X.shape[1]:
                mask = X[:, node["feat"]] <= node["thr"]
                f += self.lr * np.where(mask, node["left"], node["right"])
        p = 1.0 / (1.0 + np.exp(-np.clip(f, -20, 20)))
        return np.column_stack([1.0 - p, p])

    def to_dict(self):
        return {
            "n_estimators": self.n_estimators,
            "learning_rate": self.lr,
            "min_samples_leaf": self.min_leaf,
            "l2_leaf": self.l2,
            "base_log_odds": round(self.base_log_odds, 6),
            "trees": self.trees,
        }

    @classmethod
    def from_dict(cls, d):
        if not d:
            return None
        return cls(
            n_estimators=d.get("n_estimators", 30),
            learning_rate=d.get("learning_rate", 0.06),
            min_samples_leaf=d.get("min_samples_leaf", 25),
            l2_leaf=d.get("l2_leaf", 15.0),
            base_log_odds=d.get("base_log_odds", 0.0),
            trees=d.get("trees", []),
        )


def _infer_period_kind(p):
    pk = p.get("period_kind")
    if pk:
        return pk
    h = p.get("horizon_months")
    if h is None:
        return "FY"
    if h <= 4:
        return "Q"
    if h <= 7:
        return "H"
    if h <= 15:
        return "FY"
    return "MULTI_YEAR"


def _promise_part(p, ctx):
    """Promise-level and concall-context signals."""
    cat = p["category"]
    q_txt = p.get("quote", "") or ""
    act = ctx.get("actuals")
    amb = mg = 0.0
    val = p.get("value_low")
    if act is not None and val is not None:
        p_date = date.fromisoformat(p["call_date"]) if isinstance(p.get("call_date"), str) else date.today()
        if cat in ("revenue_growth", "pat_growth", "ebitda_growth") and p.get("growth_basis") != "qoq":
            tg = act.trailing_growth(p_date)
            if tg is not None:
                amb = max(-3.0, min(3.0, (val - tg) / 10.0))
        elif cat == "revenue_target":
            ls = act.latest_sales(p_date) if hasattr(act, "latest_sales") else None
            tg = act.trailing_growth(p_date)
            if ls and ls > 0 and tg is not None:
                implied_g = (val / ls - 1.0) * 100.0
                amb = max(-3.0, min(3.0, (implied_g - tg) / 10.0))
        elif cat in ("ebitda_margin", "pat_margin") and val >= 3.0:
            tm = act.trailing_opm(p_date)
            if tm is not None:
                mg = max(-3.0, min(3.0, (val - tm) / 2.0))

    h = p.get("horizon_months")
    pk = _infer_period_kind(p)
    ver_fin = p.get("verifiable_by") == "financials" or (
        p.get("verifiable_by") is None and cat in GROUPS["fin"]
    )
    n_hedges = min(3.0, float(len(HEDGES.findall(q_txt))))

    return [
        float(cat in GROUPS["fin"]),
        float(cat in GROUPS["build"]),
        float(cat in GROUPS["commercial"]),
        float(cat in ("ebitda_margin", "debt", "cost_saving")),
        float(cat in ("commissioning", "product_launch")),
        float(ver_fin),
        float(pk in ("FY", "MULTI_YEAR")),
        float(pk in ("Q", "DATE")),
        float(p.get("strength") == "firm"),
        float(p.get("strength") in ("aspirational", "hedged")),
        float(val is not None),
        float(p.get("direction") in ("range", "at_least")),
        float(bool(p.get("reiteration")) or p.get("repeat_index", 0) > 0),
        float(bool(p.get("conditions"))),
        float(p.get("section") == "prepared"),
        float(p.get("role") in ("MD", "CEO", "Chairman", "Founder")),
        n_hedges,
        min(3.0, (h or 12.0) / 12.0),
        math.log1p(ctx.get("promises_in_call", 1)) - 2.5,
        amb,
        mg,
        _logit(ctx.get("muse_p")),
    ]


def featurize(p, ctx):
    """ctx: dict(hist, promises_in_call, actuals, muse_p). hist = history.history_features
    cut strictly before the promise's made date."""
    h = dict(ctx["hist"])
    if "cat_kept_shrunk" not in h:
        grp_map = h.get("grp_kept", {})
        h["cat_kept_shrunk"] = grp_map.get(_cat_grp(p.get("category")), h.get("kept_shrunk", 0.48))
    return [1.0] + [h[f] for f in MODEL_HIST_FEATURES] + _promise_part(p, ctx)


def _ctx(p, per_call, acts, forecasts, hist):
    fc = (forecasts or {}).get(p.get("id"))
    muse_p = (fc.get("p") or fc.get("p_delivered")) if isinstance(fc, dict) else fc
    return {"hist": hist, "promises_in_call": per_call.get(p.get("call_id", ""), 1),
            "actuals": acts.get(p["ticker"]), "muse_p": muse_p}


def _logit(p):
    if p is None:
        return 0.0
    if isinstance(p, dict):
        p = p.get("p") or p.get("p_delivered")
        if p is None:
            return 0.0
    p = min(0.97, max(0.03, float(p)))
    return math.log(p / (1 - p)) - math.log(0.43 / 0.57)   # centred on the empirical base rate


def build_dataset(resolved, snaps, forecasts=None):
    """X, y, w, meta for all scored promises; track record cut before each made date."""
    acts = {t: financials.Actuals(s) for t, s in snaps.items()}
    per_call = {}
    for p in resolved:
        per_call[p["call_id"]] = per_call.get(p["call_id"], 0) + 1
    X, y, w, Xu, meta = [], [], [], [], []
    for p in resolved:
        cut = date.fromisoformat(p["call_date"]) - timedelta(days=1)
        hist = history.history_features(resolved, p["ticker"], cut, category=p.get("category"))
        row = featurize(p, _ctx(p, per_call, acts, forecasts, hist))[1:]
        if p["resolution"].get("y") is None:
            Xu.append(row)
            meta.append({"id": p["id"], "labelled": False, "xu": len(Xu) - 1})
            continue
        X.append(row)
        y.append(1.0 if p["resolution"]["y"] >= 0.75 else 0.0)   # P(kept in full and on time)
        w.append(score.weight(p))
        meta.append({"id": p["id"], "labelled": True, "ticker": p["ticker"], "made": p["call_date"],
                     "known": p["resolution"].get("knowable_at") or "9999"})
    return np.array(X), np.array(y), np.array(w), np.array(Xu), meta


def fit(X, y, l2=L2, iters=2500, lr=0.05):
    return fit_w(X, y, np.ones(len(y)), l2, iters, lr)


def fit_w(X, y, s, l2=None, iters=2500, lr=0.05):
    """Fit Bayesian MAP logistic regression with sample weights, domain-informed prior mean,
    and variance-floored standardization."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    if l2 is None:
        l2 = 22.0 if len(X) >= 400 else 38.0
    mu = np.zeros(X.shape[1] + 1)
    sd = np.ones(X.shape[1] + 1)
    mu[1:] = X.mean(0)
    sd[1:] = np.maximum(X.std(0), 0.12)
    Z = np.clip((X - mu[1:]) / sd[1:], -3.5, 3.5)
    Zb = np.hstack([np.ones((len(X), 1)), Z])

    p0 = float(np.clip(((s * y).sum() + 50.0 * 0.43) / (s.sum() + 50.0), 0.05, 0.95))
    target_b0 = math.log(p0 / (1.0 - p0))
    w0 = np.zeros(Zb.shape[1])
    w0[0] = target_b0
    for idx, fn in enumerate(FEATURES):
        if fn in PRIOR_W0 and idx < len(w0):
            w0[idx] = PRIOR_W0[fn]

    w = w0.copy()
    reg = np.full(Zb.shape[1], l2)
    reg[0] = 25.0
    for idx, fn in enumerate(FEATURES):
        if fn in PRIOR_W0 and idx < len(reg):
            reg[idx] = max(l2, 45.0)

    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(Zb @ w, -25, 25)))
        reg_term = reg * (w - w0)
        g = (Zb * (s * (p - y))[:, None]).sum(0) / s.sum() + reg_term / s.sum()
        w -= lr * g
    return w, mu, sd


def fit_tree_model(X, y, s):
    """Fit Pure-NumPy Gradient Boosted Decision Trees on tabular features."""
    clf = NumpyHistGBClassifier(n_estimators=30, learning_rate=0.06, min_samples_leaf=25, l2_leaf=15.0)
    clf.fit(X, y, sample_weight=s)
    return clf


def predict_proba(w, X):
    return 1.0 / (1.0 + np.exp(-np.clip(np.asarray(X) @ w, -25, 25)))


def auc(y_true, s):
    """Exact tie-aware Mann-Whitney U / ROC AUC for binary y (kept = y >= 0.75)."""
    yb = np.asarray(y_true) >= 0.75
    s = np.asarray(s, dtype=float)
    pos, neg = s[yb], s[~yb]
    if len(pos) == 0 or len(neg) == 0:
        return None
    wins = np.sum(pos[:, None] > neg[None, :]) + 0.5 * np.sum(pos[:, None] == neg[None, :])
    return float(wins / (len(pos) * len(neg)))


def brier(y, s):
    return float(np.mean((np.asarray(s) - (np.asarray(y) >= 0.75)) ** 2))


def _boot_auc(y, s, n=1000):
    rng = np.random.default_rng(1)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        a = auc(y[i], s[i])
        if a is not None:
            vals.append(a)
    return [round(float(np.quantile(vals, 0.05)), 3), round(float(np.quantile(vals, 0.95)), 3)] if vals else None


def _standardize_apply(X, mu, sd):
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[None, :]
    Z = np.clip((X - mu[1:]) / sd[1:], -3.5, 3.5)
    return np.hstack([np.ones((len(X), 1)), Z])


def evaluate(X, y, w, meta):
    """Evaluate performance with Leave-One-Company-Out and Walk-Forward temporal split."""
    lab = [m for m in meta if m["labelled"]]
    tick = np.array([m["ticker"] for m in lab])
    made = np.array([m["made"] for m in lab])
    known = np.array([m["known"] for m in lab])
    hist_col = FEATURES.index("cat_kept_shrunk") - 1
    muse_col = FEATURES.index("muse_forecast_logit") - 1
    out = {"n": int(len(y)), "kept_rate": round(float(np.mean(y >= 0.75)), 3)}

    # 1) Leave-One-Company-Out
    s_linear = np.zeros(len(y))
    s_tree = np.zeros(len(y))
    s_base = np.zeros(len(y))
    for t in np.unique(tick):
        tr, te = tick != t, tick == t
        wr, mu, sd = fit_w(X[tr], y[tr], w[tr])
        s_linear[te] = predict_proba(wr, _standardize_apply(X[te], mu, sd))
        tree_m = fit_tree_model(X[tr], y[tr], w[tr])
        s_tree[te] = tree_m.predict_proba(X[te])[:, 1]
        s_base[te] = y[tr].mean()

    s_ensemble = (1.0 - ENSEMBLE_TREE_WEIGHT) * s_linear + ENSEMBLE_TREE_WEIGHT * s_tree

    out["loco"] = {
        "auc_model": round(auc(y, s_ensemble), 4),
        "auc_ci90": _boot_auc(y, s_ensemble),
        "auc_linear_only": round(auc(y, s_linear), 4),
        "auc_prior_score_only": round(auc(y, X[:, hist_col]), 4),
        "auc_muse_forecast_only": round(auc(y, X[:, muse_col]), 4) if np.any(X[:, muse_col]) else None,
        "auc_muse_ci90": _boot_auc(y, X[:, muse_col]) if np.any(X[:, muse_col]) else None,
        "brier_model": round(brier(y, s_ensemble), 4),
        "brier_linear_only": round(brier(y, s_linear), 4),
        "brier_base_rate": round(brier(y, s_base), 4),
    }

    # Ablation: without the Muse / LLM forecast feature
    s_nm = np.zeros(len(y))
    Xn = X.copy()
    Xn[:, muse_col] = 0.0
    for t in np.unique(tick):
        tr, te = tick != t, tick == t
        wr, mu, sd = fit_w(Xn[tr], y[tr], w[tr])
        s_nm[te] = predict_proba(wr, _standardize_apply(Xn[te], mu, sd))
    out["loco"]["auc_without_muse"] = round(auc(y, s_nm), 4)

    # 2) Walk-forward
    cut = sorted(made)[int(len(made) * 0.5)]
    tr, te = (made < cut) & (known < cut), made >= cut
    if tr.sum() > 30 and te.sum() > 20:
        wr, mu, sd = fit_w(X[tr], y[tr], w[tr])
        s_wf_linear = predict_proba(wr, _standardize_apply(X[te], mu, sd))
        tree_wf = fit_tree_model(X[tr], y[tr], w[tr])
        s_wf_tree = tree_wf.predict_proba(X[te])[:, 1]
        s_wf_ens = (1.0 - ENSEMBLE_TREE_WEIGHT) * s_wf_linear + ENSEMBLE_TREE_WEIGHT * s_wf_tree

        out["walk_forward"] = {
            "cutoff": str(cut), "train": int(tr.sum()), "test": int(te.sum()),
            "auc_model": round(auc(y[te], s_wf_ens), 4),
            "auc_ci90": _boot_auc(y[te], s_wf_ens),
            "auc_linear_only": round(auc(y[te], s_wf_linear), 4),
            "auc_prior_score_only": round(auc(y[te], X[te][:, hist_col]), 4),
            "auc_muse_forecast_only": round(auc(y[te], X[te][:, muse_col]), 4),
            "brier_model": round(brier(y[te], s_wf_ens), 4),
            "brier_base_rate": round(brier(y[te], np.full(te.sum(), y[tr].mean())), 4),
        }

    # Calibration buckets (LOCO ensemble predictions)
    bins = []
    for lo in (0.0, 0.35, 0.45, 0.55, 0.65):
        hi = {0.0: 0.35, 0.35: 0.45, 0.45: 0.55, 0.55: 0.65, 0.65: 1.01}[lo]
        m = (s_ensemble >= lo) & (s_ensemble < hi)
        if m.sum():
            bins.append({"bucket": f"{lo:.2f}-{min(hi, 1):.2f}", "n": int(m.sum()),
                         "predicted": round(float(s_ensemble[m].mean()), 3),
                         "kept": round(float((y[m] >= 0.75).mean()), 3)})
    out["calibration"] = bins
    return out, s_ensemble


def train(resolved, snaps, forecasts=None):
    X, y, w, Xu, meta = build_dataset(resolved, snaps, forecasts)
    if len(y) < 40:
        return None
    ev, s_loco = evaluate(X, y, w, meta)
    wr, mu, sd = fit_w(X, y, w)
    tree_clf = fit_tree_model(X, y, w)

    raw = (wr / (sd + 1e-12)).round(3).tolist()
    coefs = sorted(zip(FEATURES, raw), key=lambda kv: -abs(kv[1]))
    preds = {}
    lab = [m for m in meta if m["labelled"]]
    for m, s in zip(lab, s_loco):
        preds[m["id"]] = round(float(s), 3)   # out-of-sample for scored promises
    if len(Xu):
        su_linear = predict_proba(wr, _standardize_apply(Xu, mu, sd))
        su_tree = tree_clf.predict_proba(Xu)[:, 1]
        su_ens = (1.0 - ENSEMBLE_TREE_WEIGHT) * su_linear + ENSEMBLE_TREE_WEIGHT * su_tree
        for m, s in zip([m for m in meta if not m["labelled"]], su_ens):
            preds[m["id"]] = round(float(s), 3)

    return {
        "features": FEATURES,
        "weights": wr.tolist(),
        "mu": mu.tolist(),
        "sd": sd.tolist(),
        "tree_model": tree_clf.to_dict(),
        "coefficients": coefs,
        "evaluation": ev,
        "predictions": preds,
        "ensemble_weight": ENSEMBLE_TREE_WEIGHT,
    }


def score_new(model, p, ctx):
    """Point prediction for a single promise using the trained Linear + GBDT Ensemble."""
    mu, sd = np.array(model["mu"]), np.array(model["sd"])
    raw = np.array(featurize(p, ctx)[1:])
    z = _standardize_apply(raw, mu, sd)
    p_lin = float(predict_proba(np.array(model["weights"]), z)[0])
    tree_dict = model.get("tree_model")
    if tree_dict:
        tree_clf = NumpyHistGBClassifier.from_dict(tree_dict)
        p_tree = float(tree_clf.predict_proba(raw)[0, 1])
        w_t = float(model.get("ensemble_weight", ENSEMBLE_TREE_WEIGHT))
        return (1.0 - w_t) * p_lin + w_t * p_tree
    return p_lin


def predict_guidance_accuracy(model, resolved, ticker, category, value=None,
                              horizon_months=12, strength="firm", role="MD",
                              quote="", asof=None, actuals=None, muse_p=None):
    """Predict future accuracy of holding future guidance of a company based on past track record."""
    if asof is None:
        asof = date.today()
    elif isinstance(asof, str):
        asof = date.fromisoformat(asof)

    # 1. Pull company past guidance track record strictly point-in-time
    if actuals is None:
        snap = financials.fetch(ticker)
        actuals = financials.Actuals(snap) if snap else None

    hist = history.history_features(resolved, ticker, asof, category=category)
    track = history.guidance_track_record(resolved, ticker, asof)

    # 2. Formulate promise object with complete structural context
    val = float(value) if value is not None else None
    pk = "Q" if horizon_months <= 4 else "H" if horizon_months <= 7 else "FY" if horizon_months <= 15 else "MULTI_YEAR"
    p = {
        "id": f"PRED:{ticker}:{asof.isoformat()}",
        "ticker": ticker,
        "category": category,
        "value_low": val,
        "value_high": val,
        "horizon_months": horizon_months,
        "period_kind": pk,
        "verifiable_by": "financials" if category in GROUPS["fin"] else "disclosure",
        "strength": strength,
        "role": role,
        "section": "prepared",
        "call_date": asof.isoformat(),
        "quote": quote or f"Management guidance on {category} for {horizon_months}m",
    }

    ctx = {"hist": hist, "promises_in_call": 6, "actuals": actuals, "muse_p": muse_p}
    p_kept = score_new(model, p, ctx)

    # 3. Credibility adjustment calculation
    adjusted_value = val
    adjustment_factor = 1.0
    adjustment_note = ""

    if val is not None:
        if category in history.REV_CATS:
            factor = hist.get("rev_ratio", 0.96)
            adjusted_value = round(val * factor, 2)
            adjustment_factor = round(factor, 3)
            adjustment_note = f"Adjusted by {factor:.2f}× historical revenue guidance delivery ratio"
        elif category in history.MARGIN_CATS:
            margin_spread = hist.get("fin_spread", 0.0)
            offset = -0.8 if margin_spread < -0.05 else (+0.3 if margin_spread > 0.08 else 0.0)
            adjusted_value = round(val + offset, 2)
            adjustment_factor = round(adjusted_value / max(1e-6, val), 3)
            adjustment_note = "Adjusted for historical margin guidance variance"
        elif category in history.CAPEX_CATS:
            cap_pct = track.get("capex_guidance", {}).get("delivery_rate_pct", "N/A")
            adjustment_note = f"Historically delivered {cap_pct}% of capex/capacity projects on schedule"

    # 4. Risk and diagnostic breakdown
    risks = []
    if hist.get("ghost_rate", 0) > 0.08:
        risks.append(f"👻 High Ghost Rate: {hist['ghost_rate']:.0%} of past guidance was quietly dropped without updates.")
    if hist.get("goalpost_rate", 0) > 0.20:
        risks.append(f"⏱ Goalpost Moving: {hist['goalpost_rate']:.0%} of past targets had deadlines delayed or cut.")
    if p_kept < 0.40:
        risks.append("⚠️ Low Delivery Probability: Track record and target stretch indicate elevated risk of guidance miss.")
    elif p_kept >= 0.65:
        risks.append("✅ High Delivery Probability: Management has strong historical follow-through on commitments.")

    return {
        "ticker": ticker,
        "category": category,
        "guided_value": val,
        "adjusted_value": adjusted_value,
        "adjustment_factor": adjustment_factor,
        "adjustment_note": adjustment_note,
        "p_kept": round(p_kept, 3),
        "grade": score.grade(p_kept * 100),
        "track_record": track,
        "diagnostics": {
            "historical_say_do_score": score.company_score(resolved, ticker, asof)["score"],
            "category_say_do_score": round(hist.get("cat_kept_shrunk", hist.get("kept_shrunk", 0)) * 100, 1),
            "trend": round(hist.get("trend", 0) * 100, 1),
            "recent_delivery_rate": round(hist.get("recent4", 0) * 100, 1),
            "consecutive_streak": int(hist.get("streak", 0)),
            "effective_sample_size": round(hist.get("eff_n", 0), 1),
        },
        "risks": risks,
    }


def simulate_guidance_hurdle_curve(model, resolved, ticker, category="revenue_growth",
                                  min_val=None, max_val=None, steps=10,
                                  horizon_months=12, strength="firm", role="MD", asof=None):
    """Simulate a dynamic hurdle curve plotting P(Delivery) vs Guided Target.

    Identifies the exact guidance threshold where execution risk accelerates and
    delivery probability breaks down.
    """
    if asof is None:
        asof = date.today()
    elif isinstance(asof, str):
        asof = date.fromisoformat(asof)

    snap = financials.fetch(ticker)
    acts = financials.Actuals(snap) if snap else None

    if category in history.REV_CATS:
        tg = acts.trailing_growth(asof) if acts else None
        benchmark = round(tg, 1) if tg is not None else 20.0
        if min_val is None:
            min_val = max(5.0, round(benchmark * 0.4, 0))
        if max_val is None:
            max_val = max(min_val + 25.0, round(benchmark * 1.8, 0))
    elif category in history.MARGIN_CATS:
        tm = acts.trailing_opm(asof) if acts else None
        benchmark = round(tm, 1) if tm is not None else 14.0
        if min_val is None:
            min_val = max(4.0, round(benchmark - 4.0, 0))
        if max_val is None:
            max_val = round(benchmark + 6.0, 0)
    else:
        benchmark = 100.0
        if min_val is None:
            min_val = 50.0
        if max_val is None:
            max_val = 300.0

    step_size = (max_val - min_val) / max(1, steps - 1)
    points = []
    hurdle_50 = None
    high_conf = None
    breakdown_45 = None

    for i in range(steps):
        v = round(min_val + i * step_size, 1)
        res = predict_guidance_accuracy(
            model=model, resolved=resolved, ticker=ticker, category=category,
            value=v, horizon_months=horizon_months, strength=strength,
            role=role, asof=asof, actuals=acts
        )
        p = res["p_kept"]
        adj = res["adjusted_value"]
        points.append({
            "guided_value": v,
            "p_kept": p,
            "adjusted_value": adj,
            "grade": res["grade"]
        })

        if p >= 0.65:
            high_conf = v
        if p >= 0.50:
            hurdle_50 = v
        if p < 0.45 and breakdown_45 is None:
            breakdown_45 = v

    return {
        "ticker": ticker,
        "category": category,
        "benchmark_trailing": benchmark,
        "points": points,
        "hurdle_50_ceiling": hurdle_50,
        "high_confidence_ceiling": high_conf,
        "breakdown_risk_point": breakdown_45,
    }


def save(model, path):
    json.dump({k: v for k, v in model.items() if not k.startswith("_")}, open(path, "w"), indent=1)
