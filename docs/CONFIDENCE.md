# Strength estimates and diagnostics

Results history now contains a completed-pair strength report. Each pair must
have both color-reversed games finished; unpaired results remain in the existing
game scoreboard but are excluded from this report. All scores favor engine A.

The five pentanomial bins count pairs scoring 0, 0.5, 1, 1.5 or 2 points.
The paired mean score is converted to logistic Elo with
`400 log10(score / (1-score))`. This is logistic Elo, not Fishtest normalized Elo.

Repeated opening positions form clusters. For K opening clusters and N completed
pairs, the score variance estimate is
`K/(K-1) * sum((cluster_score_sum - mean * cluster_pair_count)^2) / N^2`.
The report transforms mean ± normal quantile × standard error into Elo intervals
at 80%, 90%, 95% and 99%. Scores are bounded to [0,1]; reaching an endpoint means
an unbounded Elo limit. Approximate LOS is the normal CDF of
`(mean - 0.5) / standard_error`.

These are approximate fixed-sample intervals. They require at least ten distinct
opening groups and nonzero between-group variation. Ten groups is a display
minimum, not a guarantee of reliable coverage. Skewed, small or selected samples
can still mislead. An all-win or all-draw sample must not yield a zero-width
interval. LOS is not a Bayesian probability or a test verdict. Repeatedly
monitoring fixed-sample intervals does not supply sequential error guarantees.
The existing exploratory 95% opening-cluster bootstrap is retained separately.

Fishtest's SPRT, normalized Elo, selected hypotheses, alpha/beta error control
and stopping boundaries are not implemented by this report. A proper sequential
test needs those controls specified before play and a dedicated validated test
implementation. This release does not claim Fishtest-equivalent decisions.

The Engine health & tablebases dialog uses the loaded match's engine snapshot,
or selected profiles when there is no match. It checks executable hashes and
lists configured Threads, Hash, Syzygy paths, top-level WDL/DTZ file counts and
probe limits. It does not launch searches or verify engine support, completeness
of tablebase sets, file integrity or actual probing. Reported tablebase hits
remain visible in live and recorded analysis.

## 0.5.14: normalized Elo and SPRT

Match Setup now enables a normalized pentanomial generalized SPRT monitor for
new matches, with H0=0, H1=+5 nElo and alpha=beta=0.05 by default. These are editable
before start and are saved with the match. Old matches do not receive a
retrospective pass/fail verdict. Results history displays the likelihood ratio,
effective stopping bounds, tested pairs and first decision. The decision is
frozen at the first boundary crossing, while the scheduled match continues.

The independent implementation uses the normalized t-value constrained
multinomial likelihood from Fishtest's published model, unseen-category
regularization of 0.001, Wald bounds and empirical overshoot correction.
Numerical likelihood values were compared with Fishtest reference commit
f7af98f81f0c740a4de3d9a3721854709dcdc2bb. It does not run the Fishtest service or
use its task scheduling and batching infrastructure.

Normalized Elo is `800/ln(10) * (mean - 0.5) / sqrt(2 * pair_variance)`.
It is unavailable for zero pair variance. Normalized confidence intervals at
80/90/95/99% use a cluster-robust delta-method normal approximation with at least
ten opening groups. These fixed-sample intervals are separate from the SPRT
stopping rule and are not sequentially adjusted. The previous section's lack of
SPRT applies to the 0.5.13 fixed-sample report, not this new monitor.

SPRT error guarantees assume independent opening pairs and an unchanged test.
Repeated openings, engine changes and adjudication policies can affect validity.
An accepted H1 supports the alternative relative to H0; it does not prove the
true gain equals or exceeds the H1 value. Use representative varied openings and
keep all conditions fixed. Numerical convergence errors are displayed, not
converted into verdicts. Normalized Elo and logistic Elo are distinct scales.
