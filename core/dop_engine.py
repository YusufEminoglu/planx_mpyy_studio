"""PlanX MPYY Statutory Reallocation & Development Partnership Share (DOP - Madde 18) Engine.

Implements statutory land readjustment requirements of Turkish Planning Law No. 3194, Article 18:
- Düzenleme Ortaklık Payı (DOP) Hesabı ve Parselasyon Tahsis Cetveli.
- Statutory DOP ceiling: DOPO <= 0.45 (45%).
- Public amenities included in DOP deductions:
  Roads, squares, parks, playgrounds, car parks, basic education, healthcare,
  worship places, public market places, technical infrastructure.
- Automatic calculation of:
  1. Toplam Kadastro Alanı (sum of input cadastral parcels)
  2. Toplam Kamuya Terk Alanı (sum of planned public spaces)
  3. DOP Oranı (DOPO = Terk / Kadastro)
  4. Parsel bazında DOP Kesintisi ve Net İmar Parseli Hakedişi
  5. Yasal tavan (%45) aşım denetimi ve KOP / Kamulaştırma gereksinimi tespiti.
"""

from dataclasses import dataclass, field
from typing import Any
from qgis.core import (
    QgsFeature,
    QgsGeometry,
)

from .attr_utils import first_float, first_text, norm_tr


def _norm(val: Any) -> str:
    return norm_tr(val)


@dataclass
class DOPParcelResult:
    fid: int
    ada: str
    parsel: str
    malik: str
    kadastro_alani_m2: float
    dop_orani: float
    dop_kesintisi_m2: float
    net_tahsis_m2: float
    yasal_durum: str  # 'UYGUN' veya 'YASAL_SINIR_ASILDI'
    aciklama: str = ""
    geometri: QgsGeometry | None = None


@dataclass
class DOPSummary:
    toplam_kadastro_m2: float = 0.0
    toplam_terk_m2: float = 0.0
    toplam_tahsis_m2: float = 0.0
    dop_orani: float = 0.0
    yasal_sinir: float = 0.45
    yasal_uygun: bool = True
    kop_veya_kamulastirma_gerekli_m2: float = 0.0
    parsel_sayisi: int = 0
    uyarilar: list[str] = field(default_factory=list)

    @property
    def dop_orani_yuzde(self) -> float:
        return round(self.dop_orani * 100.0, 2)


class DOPEngine:
    """Statutory Article 18 / DOP reallocation computation engine."""

    STATUTORY_CEILING = 0.45

    @classmethod
    def _extract_text(cls, feat: QgsFeature, preferred_keys: tuple[str, ...]) -> str:
        return first_text(feat, preferred_keys)

    @classmethod
    def calculate_dop(
        cls,
        cadastral_features: list[QgsFeature],
        public_features: list[QgsFeature] | None = None,
        manual_public_area_m2: float = 0.0,
        forced_dop_ratio: float | None = None,
        feedback: Any = None,
    ) -> tuple[list[DOPParcelResult], DOPSummary]:
        """Calculates DOP reallocation per cadastral parcel and produces summary report."""
        parcel_results: list[DOPParcelResult] = []
        summary = DOPSummary()

        if not cadastral_features:
            summary.uyarilar.append('Hesaplama için kadastro parsel verisi bulunamadı.')
            return parcel_results, summary

        # Extract cadastral lot areas
        total_cadastre = 0.0
        cadastre_data: list[tuple[int, str, str, str, float, QgsGeometry]] = []

        ada_keys = ("ADA", "ada", "ada_no", "block", "ADANO")
        parsel_keys = ("PARSEL", "parsel", "parsel_no", "lot", "PARSELNO")
        malik_keys = ("MALIK", "malik", "sahip", "ad_soyad", "owner", "ad")
        area_keys = ("TAPU_ALANI", "tapu_alani", "alan_m2", "AlanM2", "yuzolcum", "alan", "ALAN")

        for feat in cadastral_features:
            geom = feat.geometry()
            area_m2 = geom.area() if (geom and not geom.isEmpty()) else 0.0
            if area_m2 <= 0.0:
                attr_area = first_float(feat, area_keys, default=0.0)
                if attr_area is not None and attr_area > 0.0:
                    area_m2 = attr_area

            if area_m2 <= 0.0:
                continue

            fid = feat.id()
            ada = cls._extract_text(feat, ada_keys) or "-"
            parsel = cls._extract_text(feat, parsel_keys) or str(fid)
            malik = cls._extract_text(feat, malik_keys) or 'Mülkiyet Belirtilmemiş'

            cadastre_data.append((fid, ada, parsel, malik, area_m2, geom))
            total_cadastre += area_m2

        summary.toplam_kadastro_m2 = round(total_cadastre, 2)
        summary.parsel_sayisi = len(cadastre_data)

        if total_cadastre <= 0.0:
            summary.uyarilar.append('Geçerli bir kadastro alanı tespit edilemedi.')
            return parcel_results, summary

        # Determine total public deduction area
        total_public = 0.0
        if public_features:
            for pf in public_features:
                p_geom = pf.geometry()
                if p_geom and not p_geom.isEmpty():
                    total_public += p_geom.area()

        if manual_public_area_m2 > 0:
            total_public += manual_public_area_m2

        summary.toplam_terk_m2 = round(total_public, 2)

        # Calculate DOPO (honor explicit forced_dop_ratio = 0.0 as well)
        if forced_dop_ratio is not None and forced_dop_ratio >= 0.0:
            dop_ratio = round(float(forced_dop_ratio), 6)
        elif total_cadastre > 0:
            dop_ratio = round(total_public / total_cadastre, 6)
        else:
            dop_ratio = 0.0

        summary.dop_orani = dop_ratio

        # Check statutory limit (0.45)
        if dop_ratio > cls.STATUTORY_CEILING:
            summary.yasal_uygun = False
            excess_ratio = dop_ratio - cls.STATUTORY_CEILING
            summary.kop_veya_kamulastirma_gerekli_m2 = round(total_cadastre * excess_ratio, 2)
            summary.uyarilar.append(
                f'YASAL SINIR AŞILDI: Hesaplanan DOP oranı ({dop_ratio:.4f} = %{dop_ratio * 100:.2f}), İmar Kanunu Madde 18 yasal azami sınırını (%45.00) aşmaktadır! Aşan {summary.kop_veya_kamulastirma_gerekli_m2:.1f} m² için belediyece kamulaştırma yapılmalı, KOP ayrılmalı veya imar planı tadilatına gidilmelidir.'
            )
        else:
            summary.yasal_uygun = True

        # Cap landowner deduction at statutory 45% ceiling so net_tahsis_m2 never turns negative
        effective_deduction_ratio = min(cls.STATUTORY_CEILING, max(0.0, dop_ratio))
        total_tahsis = 0.0
        for fid, ada, parsel, malik, area_m2, geom in cadastre_data:
            kesinti = round(area_m2 * effective_deduction_ratio, 2)
            net_tahsis = round(max(0.0, area_m2 - kesinti), 2)
            total_tahsis += net_tahsis

            if dop_ratio > cls.STATUTORY_CEILING:
                durum = "YASAL_SINIR_ASILDI"
                aciklama = (
                    f'Hesaplanan DOP: %{dop_ratio * 100:.2f} (Yasal tavan %45.00 ile sınırlandırıldı; '
                    f'aşan kısım KOP/kamulaştırma ile karşılanmalıdır)'
                )
            else:
                durum = "UYGUN"
                aciklama = f'DOP Kesintisi: %{dop_ratio * 100:.2f} (Madde 18 uyarınca hakediş tahsis edildi)'

            parcel_results.append(
                DOPParcelResult(
                    fid=fid,
                    ada=ada,
                    parsel=parsel,
                    malik=malik,
                    kadastro_alani_m2=round(area_m2, 2),
                    dop_orani=round(dop_ratio, 4),
                    dop_kesintisi_m2=kesinti,
                    net_tahsis_m2=net_tahsis,
                    yasal_durum=durum,
                    aciklama=aciklama,
                    geometri=geom,
                )
            )

        summary.toplam_tahsis_m2 = round(total_tahsis, 2)
        return parcel_results, summary
