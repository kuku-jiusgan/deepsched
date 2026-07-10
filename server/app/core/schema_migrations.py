from sqlalchemy import inspect, text


def ensure_runtime_schema(engine) -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "instrument_fault" in table_names:
        fault_columns = {column["name"] for column in inspector.get_columns("instrument_fault")}
        if "estimated_resolved_at" not in fault_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE instrument_fault ADD COLUMN estimated_resolved_at DATETIME"))

    if "instrument" in table_names:
        instrument_columns = {column["name"] for column in inspector.get_columns("instrument")}
        if "availability_status" not in instrument_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE instrument ADD COLUMN availability_status VARCHAR(20) DEFAULT 'available'"))

    if "notification" in table_names:
        notification_columns = {column["name"] for column in inspector.get_columns("notification")}
        with engine.begin() as connection:
            if "channel" not in notification_columns:
                connection.execute(text("ALTER TABLE notification ADD COLUMN channel VARCHAR(20) DEFAULT 'site'"))
            if "delivery_status" not in notification_columns:
                connection.execute(text("ALTER TABLE notification ADD COLUMN delivery_status VARCHAR(20) DEFAULT 'success'"))
            if "error_message" not in notification_columns:
                connection.execute(text("ALTER TABLE notification ADD COLUMN error_message TEXT"))

    if "alert_rule" in table_names:
        alert_columns = {column["name"] for column in inspector.get_columns("alert_rule")}
        with engine.begin() as connection:
            if "enable_site" not in alert_columns:
                connection.execute(text("ALTER TABLE alert_rule ADD COLUMN enable_site BOOLEAN DEFAULT 1"))
            if "enable_wecom" not in alert_columns:
                connection.execute(text("ALTER TABLE alert_rule ADD COLUMN enable_wecom BOOLEAN DEFAULT 0"))
