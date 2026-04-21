# Runtime Parity Tests (ADR 0099)

Parity tests verify that different runtime routes produce the same externally
observable result.

Typical assertions:

- diagnostics parity;
- committed published-key parity;
- effective payload parity;
- execution-trace parity where ordering is contractually stable.

These tests should compare committed outputs, not internal mutable context
implementation details.
