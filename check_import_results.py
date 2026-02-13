from app import app
from models import DistributionTransformer, LineConnection, Post

with app.app_context():
    print('DistributionTransformer count:', DistributionTransformer.query.count())
    print('LineConnection count:', LineConnection.query.count())
    print('\nSample transformers:')
    for t in DistributionTransformer.query.limit(5).all():
        print('  ', t.transformer_id, t.from_primary_bus_id, '->', t.to_secondary_bus_id)
    print('\nSample transformer connections:')
    for c in LineConnection.query.filter_by(connection_type='Transformer').limit(5).all():
        print('  ', c.from_bus, '->', c.to_bus)
