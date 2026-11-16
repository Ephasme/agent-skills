Work in this order, never skipping a step and never reordering them: plan, harden, implement.

Plan. You are already in plan mode; stay there. Write `PLAN.md` at the repository root. Verify every
claim against real sources and cite each source.

Harden. Run `/skill:harden-plan <PLAN.md path>` bare: FIX is the default and has no flag. Triage
findings as critical, major or minor; fix critical and major, leave minor unless judgement requires a
change; ask only about genuine judgement calls. Repeat hardening until one round applies no fixes,
then run the closing structural sweep: if the sweep changes anything, re-loop. If three rounds still
surface critical findings, stop and report the blocker instead of patching further.

Commit the hardened plan, then append as the last line of `PLAN.md` the exact marker
`<!-- hardened: <sha of the plan commit> -->` and commit that line too. Without this marker the work
stays at HRD and the overlord will not approve it.

Only then implement, following `work.md`. Never implement before the hardening loop converges.
