from sqlalchemy import inspect, text


def ensure_runtime_schema(engine) -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "user" in table_names:
        with engine.begin() as connection:
            connection.execute(text(
                "UPDATE user SET role = '分析所所长' WHERE role = '项目负责人'"
            ))

    if "project" in table_names:
        project_columns = {column["name"] for column in inspector.get_columns("project")}
        obsolete_columns = project_columns & {"sla_level", "profit_weight"}
        with engine.begin() as connection:
            if "estimated_hours" not in project_columns:
                connection.execute(text("ALTER TABLE project ADD COLUMN estimated_hours FLOAT"))
            for column_name in sorted(obsolete_columns):
                connection.execute(text(f"ALTER TABLE project DROP COLUMN {column_name}"))
            connection.execute(text("UPDATE project SET priority = 1 WHERE priority IS NULL OR priority < 1"))
            connection.execute(text("UPDATE project SET priority = 3 WHERE priority > 3"))
    if "task" in table_names:
        task_columns = {column["name"] for column in inspector.get_columns("task")}
        if "schedule_dirty" not in task_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE task ADD COLUMN schedule_dirty BOOLEAN DEFAULT 0"))
                connection.execute(text("UPDATE task SET schedule_dirty = 0 WHERE schedule_dirty IS NULL"))

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

    if "time_slot" in table_names:
        time_slot_columns = {column["name"] for column in inspector.get_columns("time_slot")}
        if "schedule_run_id" not in time_slot_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE time_slot ADD COLUMN schedule_run_id VARCHAR(64) DEFAULT 'legacy'"))
                connection.execute(text("UPDATE time_slot SET schedule_run_id = 'legacy' WHERE schedule_run_id IS NULL"))

    if "alert_rule" in table_names:
        alert_columns = {column["name"] for column in inspector.get_columns("alert_rule")}
        with engine.begin() as connection:
            if "enable_site" not in alert_columns:
                connection.execute(text("ALTER TABLE alert_rule ADD COLUMN enable_site BOOLEAN DEFAULT 1"))
            if "enable_wecom" not in alert_columns:
                connection.execute(text("ALTER TABLE alert_rule ADD COLUMN enable_wecom BOOLEAN DEFAULT 0"))
