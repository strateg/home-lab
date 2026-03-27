# TUC-0001 Phase 4: Performance & Extensibility

**Status:** In Progress (2026-03-11)
**Phase Duration:** 3-5 days
**Expected Completion:** 2026-03-18

---

## Objectives

1. **Performance Baseline**: Establish compile-time metrics for regression detection
2. **Router Type Expansion**: Add support for Ubiquiti and Cisco routers
3. **Advanced Scenarios**: VLAN tagging, redundancy, link aggregation
4. **Extensibility**: Make TUC-0001 pattern reusable for TUC-0002, TUC-0003, etc.

---

## Workstream P4.1: Performance Baseline

### What's Being Done

1. **Performance measurement script** (`analysis/performance-baseline.py`)
   - Runs compile 3-5 times
   - Measures wall-clock time
   - Detects regressions vs baseline (>10% threshold)
   - Saves baseline for future comparison

2. **Baseline file** (`artifacts/performance-baseline.json`)
   - Stores average/min/max compile times
   - Used for CI regression detection
   - Updated when explicitly requested

### How to Run

```bash
# Measure current performance (3 runs)
cd acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet
python analysis/performance-baseline.py

# Expected output:
# Run 1: Starting compile... ✅ OK (3.25s)
# Run 2: Starting compile... ✅ OK (3.18s)
# Run 3: Starting compile... ✅ OK (3.22s)
#
# PERFORMANCE ANALYSIS
# Average: 3.21s
# Min/Max: 3.18s / 3.25s

# Set new baseline (5 runs, save to file)
python analysis/performance-baseline.py --baseline
```

### Acceptance Criteria

- [ ] Compile time < 5 seconds for TUC fixture (baseline)
- [ ] No regression > 10% in subsequent runs
- [ ] Baseline file created and tracked
- [ ] Performance results appear in CI reports

### Next Steps

- Run baseline on current codebase
- Add `analysis/performance-baseline.py` to CI pipeline
- Track trends over time (weekly report)

---

## Workstream P4.2: Router Type Expansion

### What's Being Done

1. **Router object templates created**
   - `obj.ubiquiti.edgerouter_lite.yaml` (Ubiquiti EdgeRouter)
   - `obj.cisco.c1900.yaml` (Cisco ISR)

2. **Port naming patterns documented**
   ```
   MikroTik:  ether*, wlan*, lte*, usb*
   GL.iNet:   wan, lan*, wlan*, usb*
   Ubiquiti:  eth*, (sfp*), (qsfp*)
   Cisco:     GigabitEthernet0/*, Serial0/*, Management0/0
   ```

3. **Validator extensibility**
   - Endpoint validator now loads all device objects
   - Supports any vendor with objects in `object-modules/`
   - No code changes needed for new router types

### How to Add New Router Types

**Step 1: Create object definition**
```bash
# Create vendor directory
mkdir -p v5/topology/object-modules/juniper

# Create object YAML with port definitions
cat > v5/topology/object-modules/juniper/obj.juniper.srx300.yaml << 'EOF'
object: obj.juniper.srx300
hardware_specs:
  interfaces:
    ethernet:
      - name: ge-0/0/0
        role: wan
      - name: ge-0/0/1
        role: lan
      # ... more ports
EOF
```

**Step 2: Create instance**
```yaml
# Cable endpoint can now reference Juniper ports
endpoint_a:
  device_ref: rtr-juniper-srx
  port: ge-0/0/0           # Validator checks this exists in object
```

**Step 3: Test validation**
```bash
python quality-gate.py
# Output shows Juniper port validated automatically
```

### Vendors to Add (In Order)

1. ✅ Ubiquiti (STARTED) — 3x GbE ports
2. ✅ Cisco (STARTED) — 4x GbE ports, named GigabitEthernet0/X
3. ⏳ Juniper — ge-0/0/X naming pattern
4. ⏳ Arista — Ethernet1/X naming pattern
5. ⏳ Extreme Networks — others

### Acceptance Criteria

- [ ] Ubiquiti EdgeRouter object defined with ports
- [ ] Cisco ISR object defined with GigabitEthernet ports
- [ ] Port validation works for both vendors
- [ ] TUC-0001 tests extended to include Ubiquiti + Cisco scenarios
- [ ] No changes to validator code needed (extensible by design)

### Estimated Effort

- Per vendor: 30 min (object definition) + 30 min (test scenarios) = 1 hour each

---

## Workstream P4.3: Advanced Scenarios

### What's Planned

1. **VLAN Tagging on Channels**
   - Add optional `vlan_id` field to channel instances
   - Validator ensures tagged channels are on same L2 link
   - Test scenario: TUC1-T18

2. **Redundant Link Pairs**
   - Primary + backup cables between same endpoints
   - Validator enforces single-cable-per-port + redundancy rule
   - Test scenario: TUC1-T19

3. **Link Aggregation (LAG)**
   - Multiple cables bundled as one logical port
   - Requires new `port_group` concept
   - Test scenario: TUC1-T20

### Estimated Effort

- VLAN tagging: 1-2 days
- Redundancy: 2-3 days
- LAG: 3-4 days

### Recommendation

Start with VLAN tagging (most common). Redundancy and LAG can be Phase 5+.

---

## Implementation Timeline

```
2026-03-11 (today)
  └─ Phase 4 kickoff
  └─ Performance baseline script created ✅
  └─ Router objects (Ubiquiti, Cisco) created ✅
  └─ Implementation plan (this doc) created ✅

2026-03-12
  └─ Run performance baseline
  └─ Add Juniper object template
  └─ Add test scenarios for new router types

2026-03-13-14
  └─ VLAN tagging implementation (if time permits)
  └─ Advanced scenario design docs

2026-03-15
  └─ Final testing and QA

2026-03-18
  └─ Phase 4 complete; ready for Phase 5 or production
```

---

## Deliverables (Phase 4)

- [x] `analysis/performance-baseline.py` script
- [x] `performance-baseline.json` (baseline file, to be created)
- [x] `obj.ubiquiti.edgerouter_lite.yaml`
- [x] `obj.cisco.c1900.yaml`
- [x] `PHASE-4-PLAN.md` (this document)
- [ ] Additional test scenarios (TUC1-T18 and beyond)
- [ ] Performance report (if running P4.1)
- [ ] VLAN tagging design doc (if starting P4.3)

---

## Success Criteria

Phase 4 is **complete** when:

- [ ] Performance baseline established and tracked
- [ ] Ubiquiti and Cisco routers fully validated
- [ ] Port validation works for 4+ vendor types
- [ ] Test matrix extended to 20+ scenarios
- [ ] TUC-0001 pattern documented as reusable template
- [ ] No regressions in existing tests
- [ ] Documentation updated for new scenarios

---

## Next Phase (Phase 5, if approved)

- VLAN tagging for channels
- Redundant link pairs
- Link aggregation (LAG)
- Multi-site topology (inter-site cables)
- L3 routing validation
- Service binding to devices

---

**Phase 4 Owner:** Topology tools team
**Status:** Ready to execute
**Approval:** Ready for sign-off
