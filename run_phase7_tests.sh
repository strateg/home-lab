#!/bin/bash
# Run Phase 7 integration tests

echo "=========================================================================="
echo "Phase 7: Integration & E2E Tests"
echo "=========================================================================="
echo ""

echo "Step 1: Run new E2E tests..."
pytest tests/integration/test_generators_e2e_phase7.py -v

TEST_RESULT=$?

echo ""
echo "Step 2: Run all unit tests..."
pytest tests/unit/generators/ -v --cov=topology-tools --cov-report=term-missing

UNIT_RESULT=$?

echo ""
echo "=========================================================================="
if [ $TEST_RESULT -eq 0 ] && [ $UNIT_RESULT -eq 0 ]; then
    echo "✅ ALL TESTS PASSED!"
    echo ""
    echo "Next step: Check coverage"
    pytest tests/unit/generators/ --cov=topology-tools --cov-fail-under=75
else
    echo "❌ SOME TESTS FAILED"
    echo "Review errors above and fix"
fi
echo "=========================================================================="
