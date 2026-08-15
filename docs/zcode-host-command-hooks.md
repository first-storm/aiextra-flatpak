# Running ZCode commands outside the Flatpak sandbox

ZCode can use a `PreToolUse` hook to run Bash tool commands on the host or
inside a Distrobox container instead of inside the Flatpak sandbox.

Open **Settings → Hooks** in ZCode and add a hook with these settings:

| Setting | Value |
| --- | --- |
| Scope | `User` |
| Event | `PreToolUse` |
| Runner | `Process` |
| Matcher | `Bash` |
| Command | `jq` |

## Run commands inside a Distrobox container

Add the following two arguments under **Arguments**. Each line is one separate
argument (`argv` entry):

```text
-c
{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",updatedInput:(.tool_input | .command = ("flatpak-spawn --host /usr/bin/distrobox enter -n dev -- /bin/bash -lc " + (.command | @sh)))}}
```

This example enters the Distrobox container named `dev`. Replace `dev` with
the name of your container if necessary.

## Run commands directly on the host

To run Bash tool commands directly on the host, use these two arguments
instead. Again, each line is one separate argument:

```text
-c
{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",updatedInput:(.tool_input | .command = ("flatpak-spawn --host /bin/bash -lc " + (.command | @sh)))}}
```

The hook applies to every matched Bash tool call and returns an `allow`
decision automatically. Only enable it when you trust the commands ZCode will
execute.
