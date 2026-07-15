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
        with engine.begin() as connection:
            if "schedule_dirty" not in task_columns:
                connection.execute(text("ALTER TABLE task ADD COLUMN schedule_dirty BOOLEAN DEFAULT 0"))
                connection.execute(text("UPDATE task SET schedule_dirty = 0 WHERE schedule_dirty IS NULL"))
            approval_columns = {
                "is_external_gate": "BOOLEAN DEFAULT 0",
                "gate_status": "VARCHAR(30) DEFAULT 'not_submitted'",
                "expected_approval_at": "DATETIME",
                "submitted_at": "DATETIME",
                "approved_at": "DATETIME",
                "approved_by": "INTEGER",
                "approval_note": "TEXT",
                "approval_schedule_status": "VARCHAR(30)",
                "approval_schedule_message": "TEXT",
                "approval_preview_token": "VARCHAR(128)",
                "approval_schedule_run_id": "VARCHAR(64)",
                "approval_moved_tasks": "INTEGER DEFAULT 0",
            }
            for column_name, column_type in approval_columns.items():
                if column_name not in task_columns:
                    connection.execute(text(
                        f"ALTER TABLE task ADD COLUMN {column_name} {column_type}"
                    ))
            connection.execute(text(
                "UPDATE task SET assignee_id = ("
                "SELECT project.manager_id FROM project WHERE project.id = task.project_id"
                ") WHERE is_external_gate = 1 AND assignee_id IS NULL"
            ))

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

    if "task_type_config" in table_names:
        with engine.begin() as connection:
            existing = connection.execute(text(
                "SELECT id FROM task_type_config WHERE code = 'approval_gate' LIMIT 1"
            )).first()
            if not existing:
                connection.execute(text(
                    "INSERT INTO task_type_config "
                    "(name, code, resource_type, description, is_active, sort_order) "
                    "VALUES ('方案签批', 'approval_gate', 'none', '外部审批限制，不占用人员或仪器', 1, 0)"
                ))
            connection.execute(text(
                "UPDATE task_type_config SET name = '方案签批', "
                "description = '外部审批限制，不占用人员或仪器' "
                "WHERE code = 'approval_gate'"
            ))
            connection.execute(text(
                "UPDATE task SET name = '方案签批' "
                "WHERE task_type = 'approval_gate' "
                "AND name IN ('客户方案签批限制', '客户方案签批', '客户签批限制')"
            ))

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

    if {"project", "task", "time_slot"}.issubset(table_names):
        with engine.begin() as connection:
            connection.execute(text(
                "UPDATE project SET status = 'pending' "
                "WHERE status = 'active' "
                "AND NOT EXISTS ("
                "SELECT 1 FROM task WHERE task.project_id = project.id "
                "AND task.status IN ('running', 'done', 'completed', 'interrupted')"
                ") "
                "AND NOT EXISTS ("
                "SELECT 1 FROM time_slot JOIN task ON task.id = time_slot.task_id "
                "WHERE task.project_id = project.id AND time_slot.actual_start IS NOT NULL"
                ")"
            ))
