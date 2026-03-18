from marshmallow import Schema, fields


class ViolationEventSchema(Schema):
    violation_type = fields.Str(required=True)
    zone_id = fields.Str(required=True)
    timestamp = fields.DateTime(format='iso', required=True)
    gps_longitude = fields.Float(required=True)
    gps_latitude = fields.Float(required=True)
    message = fields.Str(required=True)
