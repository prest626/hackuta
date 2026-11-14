def place_escalation(approval_id: str):
    from scheduler.escalate import place_escalation as impl

    return impl(approval_id)
