"""C1 (2026-11-11): passing a payer deadline is not a confirmed loss.

ICBC's physiotherapy guide s. 6.1 (effective 2026-09-27): "At ICBC's sole discretion, invoices submitted
outside of the 45-day timeframe may not be paid." The money class `permanent_discretionary` is renamed
`past_deadline_discretionary` ("past payer deadline - payment at payer's discretion") and a class
`confirmed_unpaid` ("confirmed unpaid (payer outcome recorded)") is added, reached only through the staff
outcome `payer_declined`. Existing rows are renamed; the write-once trigger is suspended for that one
statement, because `class_at_first_flag` carries the old name.

Revision ID: 202611120100
Revises: 202611112300
"""

from alembic import op

revision = "202611120100"
down_revision = "202611112300"
branch_labels = None
depends_on = None

NEW_CLASSES = ("'permanent_certain','past_deadline_discretionary','confirmed_unpaid','delayed_cash',"
               "'admin_time','warning'")
OLD_CLASSES = "'permanent_certain','permanent_discretionary','delayed_cash','admin_time','warning'"
NEW_OUTCOMES = ("'submitted','verified_in_portal','portal_not_received','payer_declined',"
                "'corrected_resubmitted','treatment_plan_requested','written_off','not_an_error'")
OLD_OUTCOMES = ("'submitted','verified_in_portal','portal_not_received',"
                "'corrected_resubmitted','treatment_plan_requested','written_off','not_an_error'")


def _rename(old: str, new: str, classes: str, outcomes: str) -> None:
    op.execute("ALTER TABLE item DROP CONSTRAINT item_money_class_check")
    op.execute("ALTER TABLE item_event DROP CONSTRAINT item_event_outcome_check")
    op.execute("ALTER TABLE item DISABLE TRIGGER item_write_once")
    op.execute(f"UPDATE item SET money_class = '{new}' WHERE money_class = '{old}'")
    op.execute(f"UPDATE item SET class_at_first_flag = '{new}' WHERE class_at_first_flag = '{old}'")
    op.execute("ALTER TABLE item ENABLE TRIGGER item_write_once")
    op.execute(f"ALTER TABLE item ADD CONSTRAINT item_money_class_check CHECK (money_class IN ({classes}))")
    op.execute("ALTER TABLE item_event ADD CONSTRAINT item_event_outcome_check CHECK "
               f"(outcome IS NULL OR outcome IN ({outcomes}))")


def upgrade() -> None:
    _rename("permanent_discretionary", "past_deadline_discretionary", NEW_CLASSES, NEW_OUTCOMES)


def downgrade() -> None:
    # A confirmed_unpaid item has no old equivalent: it goes back to the discretionary class.
    op.execute("ALTER TABLE item DISABLE TRIGGER item_write_once")
    op.execute("UPDATE item SET money_class = 'past_deadline_discretionary' WHERE money_class = 'confirmed_unpaid'")
    op.execute("UPDATE item SET class_at_first_flag = 'past_deadline_discretionary' "
               "WHERE class_at_first_flag = 'confirmed_unpaid'")
    op.execute("ALTER TABLE item ENABLE TRIGGER item_write_once")
    op.execute("DELETE FROM item_event WHERE outcome = 'payer_declined'")
    _rename("past_deadline_discretionary", "permanent_discretionary", OLD_CLASSES, OLD_OUTCOMES)
