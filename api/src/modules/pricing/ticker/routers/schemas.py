from src.modules.pricing.assets.config.constants import AssetIDField
from src.modules.pricing.ticker.domain.models import PointOutputModel


class AssetPointOutput(PointOutputModel):
    asset_id: AssetIDField
