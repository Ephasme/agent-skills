The repro comes first. Before touching code, write the failing test or the scripted repro that shows
the bug and run it: watch it fail for the reason you expect. A failure for another reason is not the
repro yet, so fix the harness until it fails the way the bug does. Then fix the bug and rerun the
repro to watch it pass.
