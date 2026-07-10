from __future__ import annotations

from datetime import datetime

from ortools.sat.python import cp_model


def add_scheduler_objective(
    model: cp_model.CpModel,
    tasks,
    task_starts,
    task_ends,
    task_tardiness,
    switch_penalties,
    project_inst_used_vars,
    total_units: int,
) -> None:
    weighted_tardiness = [
        task_tardiness[task.id] * int(task.priority_weight * 10)
        for task in tasks
    ]
    makespan = model.NewIntVar(0, total_units, "makespan")
    model.AddMaxEquality(makespan, [task_ends[task.id] for task in tasks])
    spans = [task_ends[task.id] - task_starts[task.id] for task in tasks]

    max_project_priority = max(
        (int(task.project.priority or 999) for task in tasks if task.project),
        default=999,
    )
    ordered_tasks = sorted(tasks, key=lambda task: (
        int(task.project.priority or 999) if task.project else 999,
        task.created_at or datetime.min,
        task.id,
    ))
    priority_completion = []
    for index, task in enumerate(ordered_tasks):
        project_priority = int(task.project.priority or 999) if task.project else 999
        project_weight = max(1, max_project_priority - project_priority + 1)
        stable_weight = len(ordered_tasks) - index
        priority_completion.append(task_ends[task.id] * project_weight * stable_weight)

    model.Minimize(
        (sum(weighted_tardiness) + makespan) * 1000
        + sum(priority_completion) * 10
        + sum(spans)
        + sum(switch_penalties) * 500
        + sum(project_inst_used_vars) * 30
    )
