# Proposal: Secondary Subtitle Disabled By Default

Serves: niStee/ani-cli-sync#101

## Why

`prepare_subtitles()` unconditionally attached the stream's English subtitle
track to the subtitle plan whenever one was present, even when the user had
asked for no secondary subtitle at all.

The consequence was a second subtitle line rendered at the top of the screen,
over the picture, for every episode - for a viewer who wants only the German
track at the bottom. The English track was not merely present but active: the
plan configured a secondary track identifier, and the player rendered it
alongside the primary.

This was not a documented feature. It was a fallback: when no secondary track
had been produced, the English track was attached so it could be toggled on
demand. The side effect was that it was on by default.

## What Changes

- When no secondary subtitle language is requested, the plan attaches only the
  primary track and the secondary track identifier is disabled.
- When a secondary language is requested, the existing behaviour is retained:
  the requested track is produced (cache lookup, or on-demand translation) and
  attached as the secondary track.
- When the requested secondary language is English and the stream carries an
  English track, that track is attached directly. It is not translated: the
  requested language is already the language of the source track, and
  translating it would be a pointless round trip that still burns a model call.
- The stream's English track moves into the primary-track chain, so the
  primary fallback no longer depends on the secondary branch firing.

## One behaviour this repairs

When the German translation fails and a secondary language was requested, the
old code produced a plan whose only track was the requested secondary, at
`sid=1`. The requested secondary had silently become the primary and the
English fallback was missing. The new plan keeps the English fallback as the
primary and puts the requested track at the secondary index. The change is
measured, not assumed, and both edge cases are pinned by tests.

## Out of Scope

- Primary subtitle selection, primary translation fallback and cue alignment.
  All unchanged.
- The unknown-duration and skip-handling paths in playback.
- The choice of which language the primary track is. Unchanged.

## Notes

Restoring the previous behaviour is a single flag: `--sub-secondary en` or
`ANI_CLI_SYNC_SUB_SECONDARY=en`. The change therefore removes a default, it
does not remove a capability.

## Related

- Local commit `dd1d5fa`, the origin of this change.
