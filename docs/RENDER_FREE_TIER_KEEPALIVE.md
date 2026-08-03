# Render Free-Tier Keep-Alive Policy

## Background

2026-07-30: Render sent a usage-limit warning email — the free-tier web
service (`rishiri-kelp-forecast-system`) was approaching its monthly 750
instance-hour cap. Root cause: UptimeRobot was pinging `/health` every 5
minutes 24 hours a day (added earlier to prevent Render's free-tier sleep
from breaking LINE webhook reply-token timing on ad-hoc user messages —
LINE reply tokens expire in roughly 30–60 seconds, and a cold start from
sleep takes 30+ seconds). Keeping the instance awake 24/7 consumes
~720–744 hours/month, essentially the entire free-tier allowance by itself.

## Policy (decided 2026-07-30)

**The service is intentionally allowed to sleep from 20:00 to 01:00 JST
daily** — the hours kelp fishermen (the app's users) are expected to be
asleep and not sending ad-hoc LINE messages. Outside that window (01:00–20:00
JST), the service is kept continuously awake.

This cuts awake time from 24h/day to 19h/day (~570–589h/month), comfortably
under the 750h free-tier cap even accounting for other free-tier services on
the same Render account.

### What this means in practice

- **Ad-hoc LINE messages sent 20:00–01:00 JST**: if the service is asleep,
  the first reply may be delayed 30+ seconds (cold start), and in the worst
  case a webhook reply token could expire before the reply is sent. This is
  an accepted tradeoff for this time window — very few, if any, of this
  app's users are expected to message the bot at these hours.
- **Scheduled LINE push notifications (16:00 and 01:30 JST)**: push
  notifications have no reply-token expiry constraint, and
  `.github/workflows/line-notifications.yml`'s "Wake service" step already
  retries the health check (5 attempts, 15s apart) before sending, so a cold
  start alone just adds a short, invisible delay. **However, this only helps
  if the backup workflow itself actually fires** — see the 2026-08-02
  incident below, where it didn't, and the notification was missed entirely.
- **Open-Meteo prefetch jobs** (`fetch-open-meteo-cache.yml`): unaffected —
  they write directly to Upstash Redis and never call Render.

## Implementation

`.github/workflows/render-keepalive.yml` requests `*/30 0-10,16-23 * * *` UTC
(every UTC hour except 11:00–15:59, i.e. 20:00–00:59 JST) — pings `/health`
every 30 minutes during 01:00–20:00 JST, none outside that window, so
Render's free-tier auto-sleep (after ~15 minutes of no traffic) takes over
naturally during 20:00–01:00 JST.

**2026-08-01 incident**: every run failed with `curl: (28) Operation timed
out after 20002 milliseconds` — the initial `--max-time 20` was too short
for this app's cold start (heavy pandas/numpy/scipy dependencies routinely
take longer than 20s to boot), so a "Run failed" email fired on every single
cold start, exactly the case this workflow exists to absorb quietly. Fixed
to `--retry 5 --retry-delay 15 --max-time 30`, matching the already-proven
pattern in `line-notifications.yml`'s "Wake service" step.

**2026-08-02 incident (more serious)**: the 16:00 JST LINE notification was
missed entirely. Render logs showed the instance was still cold-booting at
16:15 JST (15 minutes after the target time), and there was zero
`notify_all` log activity anywhere in that window — neither the primary
in-process scheduler nor the `line-notifications.yml` 16:05 JST backup ever
ran. Separately, `fetch-open-meteo-cache.yml`'s evening prefetch slot also
failed to fire that same day. Two unrelated scheduled workflows silently
missing their triggers on the same day pointed to GitHub Actions scheduler
contention: this workflow's original `*/5` request (up to 228 triggers/day)
is exactly the kind of high-frequency schedule GitHub's own docs warn can
cause other scheduled runs in the same repository to be delayed or dropped.
Reduced to `*/30` (matching UptimeRobot's own interval) to relieve that
pressure — the actual LINE notification and Open-Meteo prefetch jobs matter
far more than precise keep-alive timing. Also added a second backup
trigger to `line-notifications.yml` (16:15/01:45 JST) as a second line of
defense; `notify_all()`'s existing per-day run-lock
(`_try_notify_run_lock`) makes this safe — it won't double-send if an
earlier trigger already succeeded.

Also observed: GitHub Actions' `schedule` trigger does not reliably honor
requested cadences under load (documented, best-effort behavior). This
means the service likely still falls back asleep and cold-starts
periodically even within the intended 01:00–20:00 "awake" window — the
retry-tolerant curl above keeps this from generating failure emails, but
"always warm 01:00–20:00" remains a best-effort goal here, not a guarantee.

## UptimeRobot reconfiguration (done outside this repo, 2026-08-01)

UptimeRobot's monitor (#803177862) for `/health` no longer needs to ping
every 5 minutes for keep-alive purposes — this workflow now covers that
during 01:00–20:00 JST. Its interval was changed from 5 minutes to
**30 minutes**, so it now serves purely as an uptime/status monitor rather
than a second keep-alive mechanism (which would have kept the instance
awake 24/7 regardless of this workflow, defeating the sleep window).

**Accepted tradeoff**: UptimeRobot's free plan has no time-of-day-aware
schedule (its "Maintenance Windows" feature that would suppress alerts for
a specific daily window, e.g. 20:00–01:00 JST, requires a paid plan,
$9+/month — evaluated and declined 2026-08-01). Gmail filters were also
considered and ruled out: Gmail filter conditions cannot match on time of
arrival, only sender/subject/content, so a sender-based filter would hide
genuine daytime outage alerts too. As a result, a 30-minute check landing
during the intentional 20:00–01:00 JST sleep window may see a cold-start
timeout and report "down", followed by "up" on the next check once the
instance has woken back up — this is expected, not a real outage, and is
an accepted cost of staying on the free tier. If this email noise becomes
too disruptive in practice, revisit the paid Maintenance Windows option.

## 2026-08-03: keep-alive moved to cron-job.org

**Incident**: the 01:30 JST morning LINE notification arrived at 03:21 JST —
almost two hours late. Investigation found Render's process had restarted
twice in that window (`Handling signal: term` at 18:11 UTC, reboot at 18:21
UTC), meaning the `*/30`-minute keep-alive ping introduced in the
2026-08-02 fix above was too infrequent — Render's free tier sleeps after
roughly **15 minutes** of no traffic, so a 30-minute gap let it fall back
asleep between every single ping, silently defeating the "always warm
01:00–20:00 JST" goal the moment that change shipped. Separately, GitHub
Actions itself ran roughly two hours late that day across multiple
unrelated scheduled workflows in this repo (the notification backups *and*
this keep-alive ping), confirming GitHub Actions' `schedule` trigger is not
dependable at any frequency for this repo, not just at high frequency as
the 2026-08-02 note assumed.

**Fix**: `render-keepalive.yml`'s `schedule` trigger was removed entirely
(kept as `workflow_dispatch`-only for manual/emergency use). Keep-alive
duty moved to a `render-keepalive` job on **cron-job.org** — the same
service already proven far more punctual for the LINE notification and
Open-Meteo prefetch triggers (see `docs/OPEN_METEO_TEMPORARY_PREFETCH.md`).
cron-job.org pings `/health` every 10 minutes (safely under the ~15-minute
sleep threshold) during 01:00–19:59 JST, configured directly in the job's
own Asia/Tokyo timezone setting — no UTC conversion needed, unlike the old
GitHub Actions cron. Since cron-job.org is a separate service from GitHub
Actions, moving keep-alive here also removes any remaining scheduling
contention with the notification/prefetch GitHub Actions workflows.

## Revisit if

- The 750h/month usage still approaches the cap after this change (check
  whether another free-tier service on the same Render account is also
  consuming hours).
- User feedback indicates ad-hoc LINE messages are actually being sent
  during 20:00–01:00 JST and the delayed/missed replies are a real problem —
  in that case, consider narrowing the sleep window instead of removing it,
  or upgrading to a paid Render plan (no sleep, no hour cap).
- The nightly false "down"/"up" UptimeRobot email pair becomes too noisy —
  revisit UptimeRobot's paid Maintenance Windows ($9+/month) at that point.
