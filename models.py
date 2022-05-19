from peewee import *
from datetime import datetime

db = SqliteDatabase("sensoringas.db")

class BaseModel(Model):
    class Meta:
        database = db

class Machine(BaseModel):
    id = IntegerField(primary_key=True)
    name = TextField(unique=True)
    last_port = TextField(default="")
    sensors_number = IntegerField(default=12)
    multirange = BooleanField(default=True)

class SensorPosition(BaseModel):
    machine_name = ForeignKeyField(Machine.name, backref="sensor_positions")
    sensor_num = IntegerField()
    r4 = FloatField()
    rs_u1 = FloatField()
    rs_u2 = FloatField()
    k = FloatField()
    x = TextField()
    y = TextField()
    datetime = DateTimeField(default=datetime.now)

db.connect()
db.create_tables((Machine, SensorPosition))