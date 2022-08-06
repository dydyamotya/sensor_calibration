from peewee import Model, IntegerField, TextField, BooleanField, SqliteDatabase
from peewee import fn, FloatField, DateTimeField, ForeignKeyField
from datetime import datetime

db = SqliteDatabase("sensoringas.db", pragmas={'foreign_keys': 1})

fn = fn


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
    sensor_num = IntegerField()
    r4 = FloatField()
    rs_u1 = FloatField()
    rs_u2 = FloatField()
    k = FloatField()
    x = TextField()
    y = TextField()
    datetime = DateTimeField(default=datetime.now)
    machine = ForeignKeyField(Machine, backref="sensors")


db.connect()
db.create_tables((Machine, SensorPosition))
