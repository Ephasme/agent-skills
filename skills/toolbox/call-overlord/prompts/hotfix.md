The repro comes first. Before touching any code, write the failing test or the scripted repro that
shows the bug, and run it: watch it fail for the reason you expect. A failure for another reason is
not the repro yet — fix the harness until it fails the way the bug does. Only then fix the bug, and
run the repro again to watch it pass.
