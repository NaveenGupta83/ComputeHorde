import bittensor
from celery.utils.log import get_task_logger
from django.conf import settings

from compute_horde_miner.celery import app
from compute_horde_miner.miner import quasi_axon
from compute_horde_miner.miner.models import Validator

logger = get_task_logger(__name__)


@app.task
def announce_address_and_port():
    quasi_axon.announce_address_and_port()


@app.task
def fetch_validators():
    metagraph = bittensor.metagraph(netuid=settings.BITTENSOR_NETUID, network=settings.BITTENSOR_NETWORK)
    validator_keys = {n.hotkey for n in metagraph.neurons if n.validator_permit}
    to_activate = []
    to_deactivate = []
    to_create = []
    for validator in Validator.objects.all():
        if validator.public_key in validator_keys:
            to_activate.append(validator)
            validator.active = True
            validator_keys.remove(validator.public_key)
        else:
            validator.active = False
            to_deactivate.append(validator)
    for key in validator_keys:
        to_create.append(Validator(public_key=key, active=True))

    Validator.objects.bulk_create(to_create)
    Validator.objects.bulk_update(to_activate + to_deactivate, ['active'])
