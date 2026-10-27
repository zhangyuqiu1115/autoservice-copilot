"""在临时数据库验证旧数据升级、版本回填和迁移可逆性。"""

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, inspect, select


def test_review_migration_preserves_existing_ticket(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    database_url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    environment = dict(os.environ, DATABASE_URL=database_url)

    def migrate(action: str, revision: str) -> None:
        subprocess.run(
            [sys.executable, "-m", "alembic", action, revision],
            cwd=project_root, env=environment, check=True,
            capture_output=True, text=True, timeout=45,
        )

    migrate("upgrade", "170cbaa9d1b3")
    engine = create_engine(database_url)
    now = datetime.now(UTC)
    try:
        with engine.begin() as connection:
            metadata = MetaData()
            vehicles = Table("vehicles", metadata, autoload_with=connection)
            tickets = Table("service_tickets", metadata, autoload_with=connection)
            assert "version" not in tickets.c
            connection.execute(vehicles.insert().values(
                id=1, vin="LHGCM82633A004352", brand="BYD", model="Han EV",
                model_year=2025, powertrain_type="bev", created_at=now, updated_at=now,
            ))
            connection.execute(tickets.insert().values(
                id=1, ticket_number="ASC-OLD-TICKET", vehicle_id=1,
                customer_question="Existing question", risk_level="high",
                status="pending_review", requires_human_review=True,
                created_at=now, updated_at=now,
            ))

        migrate("upgrade", "head")
        with engine.connect() as connection:
            tickets = Table("service_tickets", MetaData(), autoload_with=connection)
            row = connection.execute(select(tickets)).mappings().one()
            assert row["version"] == 1
            assert row["customer_question"] == "Existing question"
            assert row["status"] == "pending_review"
            assert "ticket_events" in inspect(connection).get_table_names()

        migrate("downgrade", "170cbaa9d1b3")
        with engine.connect() as connection:
            tickets = Table("service_tickets", MetaData(), autoload_with=connection)
            assert "version" not in tickets.c
            number = connection.execute(select(tickets.c.ticket_number)).scalar_one()
            assert number == "ASC-OLD-TICKET"
            assert "ticket_events" not in inspect(connection).get_table_names()
        migrate("upgrade", "head")
    finally:
        engine.dispose()
