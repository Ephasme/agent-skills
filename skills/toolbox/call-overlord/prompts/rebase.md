Resolve every conflicted file, keeping both sides' intent. Do not modify files that have no
conflicts.

Keep the content both sides introduced: never delete what one side added to make the rebase apply.
Only where the two sides are genuinely mutually exclusive does one supersede the other, and then say
which and why. Resolve conflicts in `AGENTS.md` and `CLAUDE.md` and make no other edit to them.

Then look for the conflicts git did not flag: `git range-diff <oldBase>..<oldHead> <newBase>..HEAD`,
and the upstream diff over this branch's files (`git diff <oldBase> <newBase> -- $(git diff
--name-only <newBase> HEAD)`). A renamed or removed symbol this branch still uses, a changed
signature, logic upstream now also does, a colliding migration or config key — each is a finding to
fix, not a rebase artifact.

When both sides changed the same logic incompatibly and the task does not decide it, `git rebase
--abort` and report the question. Do not invent the intent.
