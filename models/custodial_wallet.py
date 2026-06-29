"""Server-held custodial wallet metadata (encrypted leaf keys)."""
from datetime import datetime
from uuid import uuid4

from extensions import db


class CustodialWallet(db.Model):
    __tablename__ = 'custodial_wallet'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    chain = db.Column(db.String(32), nullable=False, default='btc_taproot')
    address = db.Column(db.String(128), nullable=False, index=True)
    derivation_path = db.Column(db.String(64), nullable=False)
    encrypted_secret = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('custodial_wallets', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'chain', name='uq_custodial_wallet_user_chain'),
    )
