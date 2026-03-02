from schema.location_schema import GpsSchema
from marshmallow import Schema, fields

class ParkingSchema(Schema):
    empty_count = fields.Integer()
    gps = fields.Nested(GpsSchema)