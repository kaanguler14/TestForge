# TODO

Open work items in rough priority order. The first four are quality
gaps that the benchmark exposed; the last one is housekeeping with a
hard deadline on it.

## Quality

- [ ] **Suggester fallback should not fabricate findings.**
  When the model's output cannot be parsed as JSON the fallback
  currently invents a `logic_bug` entry with `input="See raw suggester
  output"`, which counts as a false positive in the benchmark on
  clean code. Replace it with `verdict=PARSE_ERROR, findings=[]` so
  parse failures are surfaced honestly. See `agents/suggester.py`,
  `_fallback_payload`.

- [ ] **Writer must produce an edge case for every parameter.**
  `FUNCTION_PROMPT` and `API_PROMPT` should require at least one
  edge-case test (zero, negative, None, empty) for every numeric or
  collection parameter, even when the source code does not visibly
  handle them. Today the writer skips these on cases like
  `06_divide_crash` so the analyzer never sees a failure and the bug
  is missed in a single iteration.

- [ ] **Loosen `expected.json` schema.**
  The current schema accepts a single `category + keywords` set. A
  case like `10_parse_int_crash` can have a valid bug that is in a
  different but equally correct category; it currently counts as
  MISS. Move to an `any_of: [...]` form so multiple acceptable
  answers can be listed.

- [ ] **Root-cause `04_guarded_factorial` and `05_validated_user_api`
  timeouts.** Both cases time out in every benchmark run, including
  the 180s one. Almost certainly an iteration-1 test that wedges the
  loop rather than a hardware issue. The artifacts under
  `runs/<run_id>_function/` for these cases have not been read yet.

## Maintenance

- [ ] **Bump pinned GitHub Actions to Node 24 versions.**
  `actions/checkout@v4` and `actions/setup-python@v5` both still run
  on Node 20. GitHub removes Node 20 from runners on 2026-09-16,
  after which the current workflow will fail. Bumping to `@v5` and
  `@v6` respectively is a one-line change in
  `.github/workflows/ci.yml`.
