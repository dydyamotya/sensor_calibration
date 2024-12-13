from peewee import SqliteDatabase
import logging

logger = logging.getLogger(__name__)

def migration_add_column_to_table(dbconn: SqliteDatabase):
    machine_columns = [column for column, *_ in dbconn.execute_sql("SELECT * FROM machine").description]
    if "heater_resistance_converter" not in machine_columns:
        dbconn.execute_sql("ALTER TABLE machine ADD COLUMN heater_resistance_converter INTEGER DEFAULT 100")
        logger.debug("Executed migration_add_column_to_table")
    else:
        logger.debug("Migration migration_add_column_to_table already there")


