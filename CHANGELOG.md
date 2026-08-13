# PreFer changelog

This file is the canonical update reference for published PreFer container
revisions. Each release entry is keyed by the immutable `sha-<short-commit>`
container tag and records the full source commit, release date, llama.cpp base
image, hosted-model inventory, preset additions or removals, context and
concurrency changes, artifact or speculative-decoding changes, prestaging
impact, and compatibility notes.

Only published revisions are recorded. There is no prospective or
`Unreleased` section. After a container build succeeds, its release entry is
added in a root-only commit so documenting the published SHA does not trigger a
replacement container build.
