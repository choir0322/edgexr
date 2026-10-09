# EdgeXR Execution Plans

Use an **ExecPlan** for a feature that spans multiple modules, a hardware
experiment with several steps, a significant refactor, or work likely to take
more than one focused session. Store active plans in `docs/exec-plans/active/`
and completed plans in `docs/exec-plans/completed/`.

An ExecPlan is a learning document as well as an implementation guide. Write it
so a student who has only the repository can understand the goal, repeat the
work, and tell whether it succeeded. Update it as discoveries are made instead
of treating it as a one-time proposal.

Every plan must contain these sections:

1. **Purpose / big picture** — the user-visible behavior or question being
   investigated, why it matters, and how to observe success.
2. **Context and orientation** — the relevant files, hardware, terms, and
   assumptions in plain language.
3. **Progress** — dated checkboxes that show the honest current state.
4. **Plan of work** — small milestones, each with a concrete result and a way to
   check it.
5. **Concrete steps** — commands, expected observations, and safe retry notes.
6. **Validation and acceptance** — tests and hands-on checks that demonstrate
   behavior, not merely that code exists.
7. **Surprises and discoveries** — unexpected results with concise evidence.
8. **Decision log** — choices, alternatives considered, rationale, and date.
9. **Outcomes and retrospective** — what worked, what remains, and what was
   learned.

For hardware work, name the exact Raspberry Pi model, OS image, camera mode,
lighting or scene, and measurement duration. If a plan changes a benchmark,
state how the old and new results can be distinguished. Do not begin a large
implementation until the user has had a chance to read the plan.

Every implementation plan must include a Progress checkbox to review/update
`docs/PIPELINE.md` and the relevant `docs/learning/` guide. Its acceptance checks
must confirm that inputs, shapes, units, scheduling, freshness and source links
still match the implementation. Record an explicit reason if the diagram is
reviewed but does not need a change; this is an ongoing task, not a one-time
documentation milestone.
