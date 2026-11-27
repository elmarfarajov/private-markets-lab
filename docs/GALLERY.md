# Gallery

Every chart is rebuilt from source with `pmlab gallery`.

## Day 1: Cash flows and performance measures

**An IRR is a root, and a stream can have none, one or several** - The NPV against the rate for the pump problem, a refinance-and-repay fund, and a stream with no IRR.

![An IRR is a root, and a stream can have none, one or several](images/irr-pathologies.png)

**Borrowing to delay capital calls raises the IRR** - A subscription credit line against the IRR, the TVPI and the Kaplan-Schoar PME.

![Borrowing to delay capital calls raises the IRR](images/irr-manipulation.png)

**The J-curve** - Net cash flow, interim IRR and multiples of 300 stylised funds through their lives.

![The J-curve](images/j-curve.png)

**Five public market equivalents of the same funds** - Kaplan-Schoar, Direct Alpha, Long-Nickels, PME+ and mPME on funds with a known 3% alpha over the S&P 500.

![Five public market equivalents of the same funds](images/pme-family.png)

**A PME assumes beta is one** - Funds with zero alpha and betas from 0.6 to 1.8, measured against the S&P 500, vintage by vintage.

![A PME assumes beta is one](images/pme-beta-bias.png)

**The benchmark is half the answer** - The same funds' Direct Alpha against four total-return benchmarks.

![The benchmark is half the answer](images/benchmark-choice.png)

**The IRR measures the market, the PME the manager** - Identical managers across 25 vintages: net IRR against net Direct Alpha.

![The IRR measures the market, the PME the manager](images/vintage-irr-vs-pme.png)

## Day 2: Fees, waterfalls and carried interest as an option

**Four tiers decide who gets each pound** - The European waterfall's tiers and the GP's share of profit.

![Four tiers decide who gets each pound](images/waterfall-tiers.png)

**Carried interest is a call spread** - The carry payoff as two calls, and its Black-Scholes value.

![Carried interest is a call spread](images/carry-as-options.png)

**From gross to net** - Net IRR against gross IRR under six sets of terms.

![From gross to net](images/gross-to-net.png)

**Two and twenty takes more than twenty** - The GP's take as a share of gross profit.

![Two and twenty takes more than twenty](images/gp-share.png)

**Fees come out of the commitment** - Quarterly fees under four fee bases, and what is left to invest.

![Fees come out of the commitment](images/fee-schedules.png)

**Deal by deal, winners are paid first** - Cumulative carry under each waterfall for one fund, and the clawback.

![Deal by deal, winners are paid first](images/european-vs-american.png)

**The clawback is the rule** - How often and how much an American waterfall overpays, across 20,000 funds.

![The clawback is the rule](images/clawback.png)

**Riskier deals are worth more to the GP** - Carry and the LPs' stake against deal volatility.

![Riskier deals are worth more to the GP](images/carry-vega.png)

**A portfolio of options** - Carry value against the correlation between deals.

![A portfolio of options](images/carry-correlation.png)

**Most of a manager's pay is fixed** - Present value of fees and carry per 100 committed (Metrick-Yasuda).

![Most of a manager's pay is fixed](images/gp-revenue.png)

**Four points a year to break even** - The LPs' stake against deal alpha, and the break-even alpha.

![Four points a year to break even](images/break-even-alpha.png)

**A hurdle with a catch-up is a timing device** - Carry value against the hurdle rate for four catch-ups.

![A hurdle with a catch-up is a timing device](images/hurdle-catch-up.png)

**Engine and formula agree** - Closed-form carry against Monte Carlo through the waterfall.

![Engine and formula agree](images/closed-form-check.png)

**The fee costs more than the carry** - Gross minus net IRR by fee and carry.

![The fee costs more than the carry](images/fee-heatmap.png)

**Fees shift the distribution, carry trims the top** - Gross and net IRRs of 4,000 simulated funds.

![Fees shift the distribution, carry trims the top](images/net-distribution.png)

**Carry rewards skill** - Carry and fees against deal alpha.

![Carry rewards skill](images/carry-delta.png)

## Day 3: Fund cash-flow models and the secondary market

**The Yale model** - Takahashi-Alexander flows, NAV and J-curve.

![The Yale model](images/ta-profile.png)

**Bow, growth and pace** - What each Takahashi-Alexander parameter does.

![Bow, growth and pace](images/ta-sensitivity.png)

**Six parameters reproduce a deal-built fund** - The model fitted to bottom-up deal funds.

![Six parameters reproduce a deal-built fund](images/ta-fit-deals.png)

**Recovering the parameters from noisy data** - Re-estimated growth, bow and call rate.

![Recovering the parameters from noisy data](images/ta-recovery.png)

**One model, many futures** - Fan charts of NAV and cumulative net cash flow.

![One model, many futures](images/stochastic-fan.png)

**The market explains much of a fund's outcome** - TVPI distribution and IRR against the market.

![The market explains much of a fund's outcome](images/fund-outcomes.png)

**Vintage matters** - IRRs of 25 vintages sharing market paths.

![Vintage matters](images/vintage-dispersion.png)

**Plan for the 95th percentile of calls** - Annual capital calls and their tail.

![Plan for the 95th percentile of calls](images/capital-calls.png)

**Reported NAVs lag and understate risk** - True against reported NAV.

![Reported NAVs lag and understate risk](images/nav-smoothing.png)

**Young funds trade at deep discounts** - Secondary discount by fund age and required return.

![Young funds trade at deep discounts](images/discount-by-age.png)

**Secondary pricing in one table** - Discount by age and required return.

![Secondary pricing in one table](images/discount-heatmap.png)

**Where the discount comes from** - Assets against the unfunded commitment.

![Where the discount comes from](images/discount-decomposition.png)

**Stale NAVs widen discounts after a fall** - Discount to reported and true NAV after a 30% fall.

![Stale NAVs widen discounts after a fall](images/crash-discount.png)

**Buying at a discount** - Buyer IRR distributions at three prices.

![Buying at a discount](images/buyer-irr.png)

**A secondary buyer skips the J-curve** - Cumulative cash flow, primary against secondary.

![A secondary buyer skips the J-curve](images/secondary-vs-primary.png)

**The shortcut prices as simulation does** - Expected-path value against Monte Carlo.

![The shortcut prices as simulation does](images/secondary-mc-check.png)

## Day 4: Venture capital: preferred stock as options

**Who gets what at exit** - Payout to each class by exit value.

![Who gets what at exit](images/vc-waterfall.png)

**Conversion one class at a time** - Exit values at which each class converts.

![Conversion one class at a time](images/vc-conversion.png)

**Series D: a floor plus a call** - Option decomposition of Series D and common.

![Series D: a floor plus a call](images/vc-options.png)

**Post-money against fair value** - Fair company value and value per share by class.

![Post-money against fair value](images/vc-post-vs-fair.png)

**Volatility and time to exit** - Overvaluation against volatility and years to exit.

![Volatility and time to exit](images/vc-sensitivity.png)

**Investor-friendly terms** - Overvaluation under different Series D terms.

![Investor-friendly terms](images/vc-terms.png)

**Backsolving the round** - Value per share against company value.

![Backsolving the round](images/vc-backsolve.png)

**Common stock value** - Fair value of a common share against years to exit.

![Common stock value](images/vc-common.png)

**A sample of stylised unicorns** - Distribution of overvaluation and common discount.

![A sample of stylised unicorns](images/vc-sample.png)

**What drives the overstatement** - Overvaluation by the latest round's terms and size.

![What drives the overstatement](images/vc-drivers.png)

**Up and down rounds** - Post-money and fair value against the round price.

![Up and down rounds](images/vc-down-round.png)

**The value of protection** - Series D against its common equivalent.

![The value of protection](images/vc-protection.png)

**OPM against Monte Carlo** - Exact integral against simulation.

![OPM against Monte Carlo](images/vc-opm-check.png)

**Different bets** - Exit multiples of Series D and common.

![Different bets](images/vc-exit-distribution.png)

**Breakpoints** - Each class's share of the marginal pound.

![Breakpoints](images/vc-breakpoints.png)

## Day 5: Nowcasting fund values: the Kalman filter

**One fund through a crash** - True value, reported NAV and the Kalman nowcast.

![One fund through a crash](images/nc-one-fund.png)

**Errors after a crash** - Mean error of four estimates around a market fall.

![Errors after a crash](images/nc-crash.png)

**Error by fund age** - RMSE of four estimates of the true value.

![Error by fund age](images/nc-errors.png)

**Coverage** - Actual against nominal coverage of the filter's intervals.

![Coverage](images/nc-coverage.png)

**Parameter recovery** - Maximum-likelihood estimates across panels.

![Parameter recovery](images/nc-recovery.png)

**How many funds** - Spread of the beta estimate by panel size.

![How many funds](images/nc-panel-size.png)

**Beta from reported NAVs** - Naive, Dimson and state-space betas by smoothing.

![Beta from reported NAVs](images/nc-beta.png)

**When filtering helps** - Filter error over reported error by smoothing and noise.

![When filtering helps](images/nc-noise-grid.png)

**Wrong parameters** - Filter error with the wrong smoothing or beta.

![Wrong parameters](images/nc-misspecified.png)

**Weight on each report** - The filter's weight on the new reported NAV.

![Weight on each report](images/nc-gain.png)

## Day 6: Smoothed returns and hidden risk

**True and reported index** - Growth of the index at true value and reported NAV.

![True and reported index](images/sm-paths.png)

**Autocorrelation** - Autocorrelation of true and reported index returns.

![Autocorrelation](images/sm-autocorrelation.png)

**Hidden risk** - Volatility, beta, Sharpe and drawdown four ways.

![Hidden risk](images/sm-risk.png)

**Unsmoothed paths** - Geltner and GLM unsmoothed index against the true one.

![Unsmoothed paths](images/sm-unsmoothed.png)

**GLM weights** - Estimated GLM smoothing weights against the appraisal rule.

![GLM weights](images/sm-glm-weights.png)

**Appraisal speed** - Measured volatility by appraisal speed.

![Appraisal speed](images/sm-speed.png)

**Appraisal noise** - Geltner volatility by appraisal noise.

![Appraisal noise](images/sm-noise.png)

**Correlation by horizon** - Correlation with the market over longer horizons.

![Correlation by horizon](images/sm-horizons.png)

**Allocation** - Maximum-Sharpe weight in private equity four ways.

![Allocation](images/sm-allocation.png)

**Robustness** - Results across many index histories.

![Robustness](images/sm-robustness.png)

## Day 7: Risk-adjusted performance with a stochastic discount factor

**The SDF** - The discount factor implied by the S&P 500 against Kaplan-Schoar's 1/R.

![The SDF](images/gp-sdf.png)

**Break-even drift** - The drift a deal needs by market exposure, under GPME and KS-PME.

![Break-even drift](images/gp-fair-alpha.png)

**Bias by beta** - Mean GPME and KS-PME of fairly priced funds by beta.

![Bias by beta](images/gp-bias.png)

**Dispersion** - How noisy one fund's GPME and KS-PME are.

![Dispersion](images/gp-dispersion.png)

**Assumed risk aversion** - Apparent NPV of a fair deal by the SDF's risk aversion.

![Assumed risk aversion](images/gp-sensitivity.png)

**Vintages on the S&P 500** - GPME and KS-PME by vintage on the actual index path.

![Vintages on the S&P 500](images/gp-vintages.png)

**Cash-flow betas** - Driessen-Lin-Phalippou estimates against planted betas.

![Cash-flow betas](images/gp-cf-beta.png)

**Cash-flow beta noise** - Spread of the beta estimate by number of funds.

![Cash-flow beta noise](images/gp-cf-noise.png)

**Testing for skill** - Rejection rates of no skill, GPME against KS-PME.

![Testing for skill](images/gp-power.png)

**Fees** - Mean GPME and KS-PME by management fee.

![Fees](images/gp-fees.png)

## Day 8: Allocating to illiquid assets

**Commitment pacing** - Private equity share of wealth under two pacing rules.

![Commitment pacing](images/al-pacing.png)

**Commitments and overcommitment** - Annual commitments and the overcommitment ratio.

![Commitments and overcommitment](images/al-commitments.png)

**Programme cash flows** - Net cash flow of the programme by year.

![Programme cash flows](images/al-cashflows.png)

**The denominator effect** - Reported and true allocation around a crash.

![The denominator effect](images/al-denominator.png)

**Calls and distributions in a crash** - Quarterly calls and distributions with and without a crash.

![Calls and distributions in a crash](images/al-crisis-flows.png)

**Forced sales** - Probability of a forced secondary sale by allocation and liquidity floor.

![Forced sales](images/al-liquidity.png)

**Cost of forced sales** - Discount paid on forced sales by allocation.

![Cost of forced sales](images/al-sale-cost.png)

**Mean-variance weights** - Optimal weights on reported and true moments.

![Mean-variance weights](images/al-mean-variance.png)

**Optimal illiquid share** - DP allocation by rebalancing frequency.

![Optimal illiquid share](images/al-dp-target.png)

**Cost of illiquidity and liquid policy** - Certainty-equivalent cost and the liquid equity share.

![Cost of illiquidity and liquid policy](images/al-dp-policy.png)

## Day 9: Hedge funds and liquid alternatives

**Trend following** - Time-series momentum on ten ETFs against the S&P 500 and DBMF.

![Trend following](images/hf-tsmom.png)

**The trend follower's smile** - Quarterly TSMOM returns against the market, with a quadratic fit.

![The trend follower's smile](images/hf-smile.png)

**Pricing the lookback straddle** - Closed forms against Monte Carlo, continuous and daily monitoring.

![Pricing the lookback straddle](images/hf-straddle-price.png)

**Trend returns on straddle factors** - R² and loadings by lookback.

![Trend returns on straddle factors](images/hf-straddle-betas.png)

**Linear clones** - Out-of-sample clones of four targets.

![Linear clones](images/hf-clones.png)

**Clone quality and weights** - Tracking error by target and the QAI clone's weights.

![Clone quality and weights](images/hf-clone-weights.png)

**Writing index puts** - The PutWrite index against the S&P 500, with drawdowns.

![Writing index puts](images/hf-putwrite.png)

**The put factor** - PutWrite alpha with and without an option factor.

![The put factor](images/hf-put-factor.png)

**Sharpe against MPPM** - Rankings by Sharpe ratio and a manipulation-proof measure.

![Sharpe against MPPM](images/hf-measures.png)

**2 and 20** - Share of gross return taken by fees, with and without a high-water mark.

![2 and 20](images/hf-fees.png)

