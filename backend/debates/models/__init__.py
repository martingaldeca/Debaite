from .participant import Participant
from .debater import Debater
from .moderator import Moderator
from .intervention import Intervention

Intervention.model_rebuild(_types_namespace={"Participant": Participant})
