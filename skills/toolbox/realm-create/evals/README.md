# The ratchet's eval pipeline

One round = one directory: `results.jsonl` (a row per case × rep), `traces/<id>_rep<k>.json`, `inspect/` logs.
Grades and tokens come from the same directory, always; a table that mixes two runs is the defect
this pipeline exists to make impossible.

## Cases

`ratchet-cases-118.json` = the 65 hand-written cases (`ratchet-cases-60.json`) + the mined ones
(`mined-cases.json`), built by `merge_cases.py`, which refuses a duplicate id.

`mined-cases.json` comes from `mine_cases.py`, which reads the queen's own omp sessions and keeps
turns where she did the work herself or asked the user about coordination. Each case carries the
user's words verbatim, the session file and turn index in `source`, and the rule it enforces in
`expectations`. A candidate is a *proposal*: it lands in `mined-cases.json` only after its checks
pass a correct transcript and fail a violating one (`test_mined_cases.py`), with no model call.

## Checks

`harness.check()` grades tool calls, not text. Two kinds matter beyond the original set:

- `command` / `no_command` — the shell's own segmentation (`_segments`). The guard reads the
  program a segment *starts* with, so `realm table | grep x` is a `realm` command and
  `grep -rn "herdr tab close" src` is a `grep`, not a `herdr tab close`. Case 8 failed on exactly
  that misreading.
- `path_tool` / `no_path_tool` — the `path` argument of `read`/`write`/`edit`, with an allowlist
  (`xd://`, `skill://`, `/tmp/`, the skill store) so mail and dispatch bodies stay legal while a
  repository path does not.

`test_harness.py` pins each kind, including the case-8 false positive and the pipe case.

## The judge

Deterministic checks cannot grade "she decided instead of asking". Those cases carry a `rubric`
or use `expectations`; `judge.py sheet` samples 50 trajectories stratified by family for human
labelling, `judge.py score` writes the judge's verdicts on the same 50, `judge.py agree` reports
accuracy, Cohen's kappa and the per-family split. A judge under ~0.8 agreement is a broken
instrument: fix the rubric, not the prompt under test.

## What decides a round

`analysis.py` reports, in order:

1. the manifest — model mix, reps per case, case sets, and a warning when a run mixes families
   (`cc-sonnet-5-5` rows in an "Opus only" table are how the last pass hid 4 non-comparable samples);
2. the paired per-case pass-rate difference with a bootstrap **clustered on family**, and a
   sign-flip permutation p-value — the primary comparison;
3. McNemar on the `2/2` binarisation **only for cases listed with `--prespecified`**: over every
   case it is a maximum over noise, and a case with true pass probability 0.8 registers as `2/2`
   only 64% of the time;
4. A/A — the two reps of one run treated as two conditions, the noise floor a change must beat;
5. tokens as median, mean and per-rep range, never one figure called a median.

## Running a round

```sh
# The evals go straight to OpenRouter: OPENROUTER_API_KEY must be exported.
.venv/bin/python -B ratchet_run.py --out ~/.omp/ratchet/realm-queen/r<N> --reps 2 --cases ratchet-cases-118.json
.venv/bin/python analysis.py --baseline <baseline dir> --branch <round dir> --cases ratchet-cases-118.json \
    --prespecified <ids named before the round>
```

`ratchet_run.py` resumes on `(case, rep)`, so an interrupted round is restarted with the same
command.
