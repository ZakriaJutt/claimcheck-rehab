"""UT-01..UT-08, UT-16..UT-19 (execution-plan.md "Planned tests"), synthetic fixtures only."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from claimcheck_core.rules.catalogue import ALL_RULE_CODES
from claimcheck_core.rules.payer_rules import wsbc_correction_limit
from tests.fixtures.factories import D, claim, outcomes, result, run, visit

# ------------------------------------------------------------------ UT-01


def test_ut01_icbc_45_day_limit_boundaries() -> None:
    v = visit(date_of_service="2026-10-01")
    r = result(run([v], on="2026-10-14"), v.id, "ICBC-01")
    assert r.outcome == "clear"  # day 13
    r = result(run([v], on="2026-10-15"), v.id, "ICBC-01")
    assert (r.outcome, r.limit_date, r.submit_by, r.money_class, r.near_limit) == (
        "flag", D("2026-11-15"), D("2026-11-14"), "delayed_cash", False)
    r = result(run([v], on="2026-11-01"), v.id, "ICBC-01")
    assert (r.outcome, r.money_class, r.near_limit) == ("flag", "delayed_cash", True)  # day 31
    r = result(run([v], on="2026-11-15"), v.id, "ICBC-01")
    assert (r.money_class, r.near_limit) == ("delayed_cash", True)  # limit day itself
    r = result(run([v], on="2026-11-16"), v.id, "ICBC-01")
    assert r.money_class == "permanent_discretionary"
    assert r.amount == Decimal("97.00")


# ------------------------------------------------------------------ UT-02


def test_ut02_wsbc_90_day_limit() -> None:
    v = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00", date_of_service="2026-07-01")
    r = result(run([v], on="2026-08-01"), v.id, "WSBC-01")
    assert (r.outcome, r.limit_date, r.submit_by) == ("flag", D("2026-09-29"), D("2026-09-28"))
    assert not r.near_limit
    assert result(run([v], on="2026-09-15"), v.id, "WSBC-01").near_limit  # day 76
    assert not result(run([v], on="2026-09-14"), v.id, "WSBC-01").near_limit  # day 75
    assert result(run([v], on="2026-09-30"), v.id, "WSBC-01").money_class == "permanent_discretionary"


# ------------------------------------------------------------------ UT-03


def test_ut03_wsbc_correction_window_arithmetic_as_catalogued() -> None:
    # The catalogue's dates (service 2026-03-01) are before the loaded WorkSafeBC versions; the
    # arithmetic is checked on the pure function, and the engine must refuse to evaluate the date.
    assert wsbc_correction_limit(D("2026-03-01"), D("2026-08-20")) == D("2026-11-18")
    assert wsbc_correction_limit(D("2026-03-01"), None) == D("2026-08-28")
    old = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00", date_of_service="2026-03-01",
                submission_state="rejected", first_rejected_on=D("2026-08-20"))
    r = result(run([old], on="2026-09-01"), old.id, "WSBC-02")
    assert (r.outcome, r.reason) == ("not_evaluated", "no_rule_version")


def test_ut03_wsbc_correction_window_inside_loaded_versions() -> None:
    known = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00", date_of_service="2026-05-01",
                  submission_state="rejected", first_rejected_on=D("2026-08-20"))
    r = result(run([known], on="2026-09-01"), known.id, "WSBC-02")
    assert (r.outcome, r.limit_date, r.money_class) == ("flag", D("2026-11-18"), "delayed_cash")
    assert not r.near_limit
    unknown = visit(payer="WSBC", billing_code="19102", amount_invoiced="95.00", date_of_service="2026-05-01",
                    submission_state="rejected", first_rejected_on=None)
    r = result(run([unknown], on="2026-09-01"), unknown.id, "WSBC-02")
    assert r.limit_date == D("2026-10-28")  # service + 180, the earliest value the rule allows
    assert result(run([unknown], on="2026-10-14"), unknown.id, "WSBC-02").near_limit  # 14 days left
    assert not result(run([unknown], on="2026-10-13"), unknown.id, "WSBC-02").near_limit
    assert result(run([unknown], on="2026-10-29"), unknown.id, "WSBC-02").money_class == "permanent_certain"


# ------------------------------------------------------------------ UT-04


def test_ut04_icbc_treatment_maximum() -> None:
    def icbc02(**kw: object) -> str:
        c = claim(**kw)
        v = visit(claim_id=c.id, date_of_service="2026-10-10", submission_state="paid", amount_paid="97.00")
        r = result(run([v], [c], on="2026-10-20"), c.id, "ICBC-02")
        return r.outcome if r.outcome != "flag" else str(r.money_class)

    assert icbc02(treatments_count=25) == "clear"
    assert icbc02(treatments_count=26) == "permanent_certain"
    assert icbc02(treatments_count=22, next_appointment_date=D("2026-10-27")) == "warning"
    assert icbc02(treatments_count=26, policy_max=35) == "clear"
    assert icbc02(treatments_count=None) == "not_evaluated"


# ------------------------------------------------------------------ UT-05


def test_ut05_one_rule_not_evaluated_others_still_answer() -> None:
    c = claim(date_of_event=D("2026-06-01"))
    v = visit(claim_id=c.id, date_of_service="2026-08-25")
    ev = run([v], [c], on="2026-09-15")
    r = result(ev, v.id, "ICBC-03")
    assert (r.outcome, r.limit_date, r.money_class) == ("flag", D("2026-08-24"), "permanent_certain")

    c2 = claim()  # crash date and end date both null
    v2 = visit(claim_id=c2.id, date_of_service="2026-08-25")
    ev2 = run([v2], [c2], on="2026-09-15")
    r = result(ev2, v2.id, "ICBC-03")
    assert (r.outcome, r.reason) == ("not_evaluated", "missing_dates")
    r1 = result(ev2, v2.id, "ICBC-01")
    assert (r1.outcome, r1.money_class) == ("flag", "delayed_cash")  # still answers
    assert len(outcomes(ev2, v2.id)) == 6  # every ICBC visit rule ran


# ------------------------------------------------------------------ UT-06


def test_ut06_second_initial_visit_and_two_sessions() -> None:
    c = claim(date_of_event=D("2026-09-20"), end_date=D("2026-12-31"))
    iv1 = visit(claim_id=c.id, billing_code="ICBC-IV", amount_invoiced="154.00", date_of_service="2026-10-01")
    iv2 = visit(claim_id=c.id, billing_code="ICBC-IV", amount_invoiced="154.00", date_of_service="2026-10-05")
    s1 = visit(claim_id=c.id, date_of_service="2026-10-08")
    s2 = visit(claim_id=c.id, date_of_service="2026-10-08")
    ev = run([iv1, iv2, s1, s2], [c], on="2026-10-10")
    assert result(ev, iv1.id, "ICBC-04").outcome == "clear"
    assert result(ev, iv2.id, "ICBC-04").outcome == "flag"
    assert result(ev, s1.id, "ICBC-05").outcome == "flag"
    assert result(ev, s2.id, "ICBC-05").outcome == "flag"
    assert result(ev, iv2.id, "ICBC-04").money_class == "warning"
    assert result(ev, iv2.id, "ICBC-04").amount is None  # "check with ICBC", no amount


# ------------------------------------------------------------------ UT-07


def test_ut07_icbc_fee_rule() -> None:
    unpaid = visit(date_of_service="2026-05-04", amount_invoiced="95.00")
    r = result(run([unpaid], on="2026-05-10"), unpaid.id, "ICBC-06")
    assert (r.outcome, r.money_class, r.amount, r.reason) == ("flag", "admin_time", None, "jane_setup")

    paid = visit(date_of_service="2026-05-04", amount_invoiced="95.00", amount_paid="95.00",
                 submission_state="paid")
    r = result(run([paid], on="2026-06-10"), paid.id, "ICBC-06")
    assert (r.outcome, r.money_class, r.amount) == ("flag", "permanent_certain", Decimal("2.00"))

    old = visit(date_of_service="2026-03-15", amount_invoiced="95.00")
    ev = run([old], on="2026-04-01")
    r = result(ev, old.id, "ICBC-06")
    assert (r.outcome, r.reason) == ("not_evaluated", "no_rule_version")
    assert ev.scopes[old.id].status == "could_not_check"
    assert ev.scopes[old.id].reasons == ("no_rule_version",)


# ------------------------------------------------------------------ UT-08


def test_ut08_wsbc_combination_injury_count_and_fee() -> None:
    c = claim(payer="WSBC", date_of_event=D("2026-05-01"), policy_status="open",
              next_appointment_date=D("2026-08-30"))
    a = visit(payer="WSBC", claim_id=c.id, billing_code="19100", amount_invoiced="196.00",
              date_of_service="2026-06-30", submission_state="paid", amount_paid="196.00")  # 60 days
    b = visit(payer="WSBC", claim_id=c.id, billing_code="19102", amount_invoiced="95.00",
              date_of_service="2026-06-30", submission_state="paid", amount_paid="95.00")
    ev = run([a, b], [c], on="2026-07-05")
    assert result(ev, b.id, "WSBC-05").outcome == "flag"
    assert result(ev, a.id, "WSBC-06").outcome == "clear"
    assert result(ev, b.id, "WSBC-08").outcome == "clear"  # 19102 at 95.00

    late = visit(payer="WSBC", claim_id=c.id, billing_code="19100", amount_invoiced="196.00",
                 date_of_service="2026-07-01", submission_state="paid", amount_paid="196.00")  # 61 days
    r = result(run([late], [c], on="2026-07-05"), late.id, "WSBC-06")
    assert (r.outcome, r.money_class) == ("flag", "warning")

    c2 = claim(payer="WSBC", end_date=None, policy_status="open", next_appointment_date=D("2026-08-30"))
    visits = [visit(payer="WSBC", claim_id=c2.id, billing_code="19102", amount_invoiced="95.00",
                    submission_state="paid", amount_paid="95.00",
                    date_of_service=date(2026, 7, 1) + timedelta(days=3 * i)) for i in range(11)]
    r = result(run(visits, [c2], on="2026-08-05"), c2.id, "WSBC-07")
    assert (r.outcome, r.money_class) == ("flag", "warning")
    r10 = result(run(visits[:10], [c2], on="2026-08-05"), c2.id, "WSBC-07")
    assert r10.outcome == "clear"


# ------------------------------------------------------------------ UT-16


def test_ut16_could_not_check_and_no_rules_applied_never_clear() -> None:
    c = claim(date_of_event=D("2026-09-01"), end_date=D("2026-12-31"), treatments_count=3, policy_max=25)
    unknown = visit(claim_id=c.id, submission_state="unknown", amount_invoiced="95.00",
                    date_of_service="2026-10-01")
    old = visit(claim_id=c.id, date_of_service="2026-03-15")
    unmapped = visit(claim_id=c.id, billing_code="UNMAPPED", date_of_service="2026-10-02")
    kinesiology = visit(claim_id=c.id, discipline="support", date_of_service="2026-10-03")
    ev = run([unknown, old, unmapped, kinesiology], [c], on="2026-10-20")

    assert ev.scopes[unknown.id].reasons == ("unknown_state",)
    assert ev.scopes[old.id].reasons == ("no_rule_version",)
    assert ev.scopes[unmapped.id].reasons == ("unmapped_code",)
    for v in (unknown, old, unmapped):
        assert ev.scopes[v.id].status == "could_not_check"
        for rule in ("ICBC-01", "ICBC-07"):  # deadline rules
            assert result(ev, v.id, rule).outcome == "not_evaluated"
        assert "clear" not in outcomes(ev, v.id).values()
    # fee and claim rules still attempted: the unknown-state visit's wrong Jane price is still flagged
    assert result(ev, unknown.id, "ICBC-06").outcome == "flag"
    assert result(ev, unmapped.id, "ICBC-06").reason == "unmapped_code"
    # the claim has no in-scope visit, so its rules cannot read clear either
    assert "clear" not in outcomes(ev, c.id).values()
    assert ev.scopes[kinesiology.id].status == "no_rules_applied"
    assert outcomes(ev, kinesiology.id) == {}
    assert ev.counts() == {"in_scope": 0, "could_not_check": 3, "no_rules_applied": 1}


def test_ut16_wsbc_code_outside_pr11_is_could_not_check() -> None:
    v = visit(payer="WSBC", billing_code="19999", amount_invoiced="50.00", date_of_service="2026-10-01")
    ev = run([v], on="2026-10-20")
    assert ev.scopes[v.id].reasons == ("unmapped_code",)
    assert "clear" not in outcomes(ev, v.id).values()


# ------------------------------------------------------------------ UT-17


def test_ut17_jane_submitted_icbc_keeps_its_45_day_limit() -> None:
    v = visit(date_of_service="2026-10-01", submission_state="submitted")
    ev = run([v], on="2026-10-15")
    r = result(ev, v.id, "ICBC-07")
    assert (r.outcome, r.reason, r.limit_date, r.submit_by) == (
        "flag", "verify_in_portal", D("2026-11-15"), D("2026-11-14"))
    r1 = result(ev, v.id, "ICBC-01")
    assert (r1.outcome, r1.reason, r1.limit_date) == ("not_evaluated", "jane_submitted_unverified",
                                                       D("2026-11-15"))
    r = result(run([v], on="2026-11-10"), v.id, "ICBC-07")
    assert (r.outcome, r.limit_date) == ("flag", D("2026-11-15"))
    assert (r.limit_date - D("2026-11-10")).days == 5  # days left shown
    # staff record: ICBC's portal does not have it -> unsubmitted, ICBC-01 applies, near-limit
    not_received = visit(id=v.id, invoice_ref=v.invoice_ref, date_of_service="2026-10-01",
                         submission_state="submitted", portal_status="not_received")
    ev = run([not_received], on="2026-11-10")
    r1 = result(ev, v.id, "ICBC-01")
    assert (r1.outcome, r1.money_class, r1.near_limit, r1.limit_date) == (
        "flag", "delayed_cash", True, D("2026-11-15"))
    assert result(ev, v.id, "ICBC-07").outcome == "clear"


def test_ut17_jane_submitted_never_reads_clear_on_icbc_01() -> None:
    for day in ("2026-10-03", "2026-10-15", "2026-11-20"):
        v = visit(date_of_service="2026-10-01", submission_state="submitted")
        assert result(run([v], on=day), v.id, "ICBC-01").outcome == "not_evaluated"
    verified = visit(date_of_service="2026-10-01", submission_state="submitted", portal_status="verified")
    assert result(run([verified], on="2026-10-15"), verified.id, "ICBC-01").outcome == "clear"


# ------------------------------------------------------------------ UT-18


def test_ut18_support_sessions_count() -> None:
    c = claim(payer="WSBC", policy_status="open", next_appointment_date=D("2026-08-30"))
    treat = [visit(payer="WSBC", claim_id=c.id, billing_code="19102", amount_invoiced="95.00",
                   date_of_service=date(2026, 7, 1) + timedelta(days=3 * i)) for i in range(9)]
    support = [visit(payer="WSBC", claim_id=c.id, billing_code="19108", amount_invoiced="65.00",
                     discipline="support", date_of_service=date(2026, 7, 28) + timedelta(days=i))
               for i in (0, 2)]
    r = result(run(treat + support, [c], on="2026-08-05"), c.id, "WSBC-07")
    assert (r.outcome, r.reason, r.money_class) == ("flag", "treatment_visits_over_maximum", "warning")

    c2 = claim(payer="WSBC", policy_status="open", next_appointment_date=D("2026-08-30"))
    a = visit(payer="WSBC", claim_id=c2.id, billing_code="19102", amount_invoiced="95.00",
              date_of_service="2026-07-10", invoice_ref="S-A1")
    b = visit(payer="WSBC", claim_id=c2.id, billing_code="19107", amount_invoiced="70.00",
              discipline="support", date_of_service="2026-07-10", invoice_ref="S-A2")
    ev = run([a, b], [c2], on="2026-07-12")
    assert result(ev, a.id, "WSBC-04").outcome == "clear"
    assert (result(ev, b.id, "WSBC-04").outcome, result(ev, b.id, "WSBC-04").money_class) == (
        "flag", "permanent_certain")


# ------------------------------------------------------------------ UT-19


def test_ut19_hand_therapy_effective_date_and_no_rule_version() -> None:
    before = visit(billing_code="ICBC-HT30", amount_invoiced="110.00", date_of_service="2026-09-26")
    after = visit(billing_code="ICBC-HT30", amount_invoiced="110.00", date_of_service="2026-09-28")
    ev = run([before, after], on="2026-10-01")
    r = result(ev, before.id, "ICBC-06")
    assert (r.outcome, r.reason) == ("not_evaluated", "no_rule_version")
    assert result(ev, after.id, "ICBC-06").outcome == "clear"


def test_ut19_every_rule_on_2026_03_15_is_not_evaluated() -> None:
    ic = claim(date_of_event=D("2026-03-01"), end_date=D("2026-06-01"), treatments_count=3, policy_max=25)
    wc = claim(payer="WSBC", date_of_event=D("2026-03-01"), policy_status="open",
               next_appointment_date=D("2026-03-20"))
    vi = visit(claim_id=ic.id, date_of_service="2026-03-15", submission_state="paid", amount_paid="97.00")
    vw = visit(payer="WSBC", claim_id=wc.id, billing_code="19102", amount_invoiced="95.00",
               date_of_service="2026-03-15", submission_state="paid", amount_paid="95.00")
    ev = run([vi, vw], [ic, wc], on="2026-03-20")
    seen = {f.result.rule_code: f.result for f in ev.findings}
    assert set(seen) == set(ALL_RULE_CODES)  # every rule code was queried
    for f in ev.findings:
        assert f.result.outcome == "not_evaluated", f.result
        assert f.result.reason == "no_rule_version"
