# MPYY 1.1.6 → 1.1.7 farkları

Kaynak: Bakanlık şema paketi `planGMLShema_1_7.zip` (eplan.csb.gov.tr). Bu rapor `tools/diff_mpyy_versions.py` ile XSD dosyalarından üretilmiştir.

## Uygulama imar planı (UIP)

Nesne tipi sayısı: 90 → 96

**Yeni nesne tipleri**

- `AfetHizmetAlani` (alan): `AfetHizmetTip` (kod listesi `AfetHizmetTip`, zorunlu)
- `AraziKullanimiDevamEttirilerekKorunacakAlanlar` (alan): `AraziKorumaKullanimTip` (kod listesi `AraziKorumaKullanimTip`, zorunlu)
- `ManiaSiniri` (çizgi): `Yukseklik` (double, isteğe bağlı)
- `OzelKanunlarlaBelirlenenAlan` (nokta): `Adi` (string, zorunlu), `OzelKanunAlanTip` (kod listesi `OzelKanunAlanTip`, zorunlu)
- `SuUlasimBaglantisi` (çizgi): `Adi` (string, isteğe bağlı)
- `YapiYaklasmaMes` (çizgi): `YapiYaklasmaMesafesi` (double, isteğe bağlı)

**Geometri türü değişen tipler**

- `ManiaPlani`: MultiLineString → MultiPolygon

**Zorunluluktan çıkan alanlar**

`AfetTehlikeliAlanlar.AfetTip`, `DogalKarakter.DogalKarakterTip`, `EnerjiNakilHatti.Gerilim`, `EnerjiUretim.EnerjiTip`, `IcmesuTesis.IcmesuTur`, `KatiAtikTesis.KatiAtikTur`, `ManiaPlani.Yukseklik`, `Mera.MeraSinif`, `PlanDegisiklikSiniri.DegismeSebepTip`, `PlanSiniri.Nitelik`, `SuYuzeyi.SuYuzeyiTip`, `TehlikeliTesis.TehlikeTur`, `TeknikAltyapi.AltyapiTur`

**Kod listesi değişiklikleri**

- `AfetHizmetTip` (yeni liste): `AfetLojistikAlani`
- `AraziKorumaKullanimTip` (yeni liste): `DogalVeEkolojikAlan`, `EkolojikOnemeSahipAlan`
- `CalismaTip`: eklenen `TuzlaAlani`
- `DogalKarakterTip`: eklenen `Tuzla`
- `EnerjiTesisTip`: eklenen `YenilenebilirEnerjiKaynaginaDayaliUretimTesisAlani`
- `OzelKanunAlanTip` (yeni liste): `SinirKapisi`
- `SitTip`: eklenen `KentselArkeolojikSit`

## Nazım imar planı (NIP)

Nesne tipi sayısı: 81 → 87

**Yeni nesne tipleri**

- `AfetHizmetAlani` (alan): `AfetHizmetTip` (kod listesi `AfetHizmetTip`, zorunlu)
- `AraziKullanimiDevamEttirilerekKorunacakAlanlar` (alan): `AraziKorumaKullanimTip` (kod listesi `AraziKorumaKullanimTip`, zorunlu)
- `ManiaSiniri` (çizgi): `Yukseklik` (double, isteğe bağlı)
- `OzelKanunlarlaBelirlenenAlan` (nokta): `Adi` (string, zorunlu), `OzelKanunAlanTip` (kod listesi `OzelKanunAlanTip`, zorunlu)
- `SuUlasimBaglantisi` (çizgi): `Adi` (string, isteğe bağlı)
- `YolDuzenlemeAlanlari` (alan): `YolDuzenlemeAlanTip` (kod listesi `YolDuzenlemeAlanTip`, zorunlu)

**Geometri türü değişen tipler**

- `ManiaPlani`: MultiLineString → MultiPolygon

**Zorunluluktan çıkan alanlar**

`AfetTehlikeliAlanlar.AfetTip`, `BoruHatti.EnerjiHatTip`, `DogalKarakter.DogalKarakterTip`, `EnerjiNakilHatti.Gerilim`, `EnerjiUretim.EnerjiTip`, `IcmesuTesis.IcmesuTur`, `KatiAtikTesis.KatiAtikTur`, `ManiaPlani.Yukseklik`, `Mera.MeraSinif`, `PlanDegisiklikSiniri.DegismeSebep`, `PlanSiniri.Nitelik`, `SuYuzeyi.SuYuzeyiTip`, `TehlikeliTesis.TehlikeTur`, `TeknikAltyapi.AltyapiTur`

**Kod listesi değişiklikleri**

- `AfetHizmetTip` (yeni liste): `AfetLojistikAlani`
- `AraziKorumaKullanimTip` (yeni liste): `DogalVeEkolojikAlan`, `EkolojikOnemeSahipAlan`
- `CalismaTip`: eklenen `TuzlaAlani`
- `DogalKarakterTip`: eklenen `Tuzla`
- `EnerjiTesisTip`: eklenen `YenilenebilirEnerjiKaynaginaDayaliUretimTesisAlani`
- `OzelKanunAlanTip` (yeni liste): `SinirKapisi`
- `SitTip`: eklenen `KentselArkeolojikSit`
- `YolDuzenlemeAlanTip` (yeni liste): `KavsakDuzenlemeAlani`, `TasitKontrolluBolge`, `YayaBolgesi`

## Çevre düzeni planı (CDP)

Nesne tipi sayısı: 60 → 72

**Yeni nesne tipleri**

- `AfetHizmetAlani` (alan): `AfetHizmetTip` (kod listesi `AfetHizmetTip`, zorunlu)
- `AraziKullanimiDevamEttirilerekKorunacakAlanlar` (alan): `AraziKorumaKullanimTip` (kod listesi `AraziKorumaKullanimTip`, zorunlu)
- `EnerjiDagitimDepolama` (alan): öznitelik yok
- `ManiaPlani` (alan): `Yukseklik` (double, isteğe bağlı)
- `ManiaSiniri` (çizgi): `Yukseklik` (double, isteğe bağlı)
- `OzelKanunlarlaBelirlenenAlan` (nokta): `Adi` (string, zorunlu), `OzelKanunAlanTip` (kod listesi `OzelKanunAlanTip`, zorunlu)
- `Planlama_AltBolge` (alan): `Adi` (string, isteğe bağlı)
- `StratejikKarar` (nokta): `Adi` (string, isteğe bağlı)
- `Stratejik_AltBolge` (alan): `Adi` (string, isteğe bağlı)
- `SuUlasimBaglantisi` (çizgi): `Adi` (string, isteğe bağlı)
- `YenilenebilirEnerjiKaynaginaDayaliUretimTesisAlani` (nokta): `Adi` (string, isteğe bağlı)
- `YerlesimAlani` (alan): `YerlesimTip` (kod listesi `YerlesimTip`, zorunlu)

**Alan değişiklikleri**

- `AskeriYskGuvenlikBlg`: yeni alan `AskeriBolgeTip` (kod listesi `AskeriBolgeTip`, zorunlu)
- `SitAlanlari.SitTip`: `SitTip` (string, zorunlu) → `SitTip` (kod listesi `SitTip`, zorunlu)

**Zorunluluktan çıkan alanlar**

`AfetTehlikeliAlanlar.AfetTip`, `BoruHatti.BoruHattiTip`, `DenizUlasimBaglanti.DenizUlasimTip`, `DogalKarakter.DogalKarakterTip`, `EnerjiNakilHatti.GerilimKw`, `EnerjiUretim.EnerjiTip`, `IcmesuTesis.IcmesuTur`, `KatiAtikTesis.KatiAtikTur`, `Mera.MeraSinif`, `PlanDegisiklikSiniri.DegismeSebep`, `PlanSiniri.NitelikTip`, `SuYuzeyi.SuYuzeyiTip`, `TehlikeliTesis.TehlikeTur`, `TeknikAltyapi.AltyapiTur`

**Kod listesi değişiklikleri**

- `AcikYesilTip`: eklenen `FuarPanayirFestivalAlani`, `AgaclandirilacakAlan`
- `AfetHizmetTip` (yeni liste): `AfetLojistikAlani`
- `AraziKorumaKullanimTip` (yeni liste): `DogalVeEkolojikAlan`, `EkolojikOnemeSahipAlan`
- `AskeriBolgeTip` (yeni liste): `AskeriYasakBolge`, `GuvenlikBolgesi`, `AskeriYasakVeGuvenlikBolgesi`
- `CalismaTip`: eklenen `DepolamaAlani`, `KamuHizmetAlani`, `TuzlaAlani`
- `DemirTip`: eklenen `RayliTopluTasimaGuzergahi`
- `OzelKanunAlanTip` (yeni liste): `SinirKapisi`
- `SitTip` (yeni liste): `1DereceArkeolojikSit`, `2DereceArkeolojikSit`, `3DereceArkeolojikSit`, `KesinKorunacakHassasAlan`, `NitelikliDogalKorumaAlani`, `SurdurulebilirKorumaKontrolluKullanimAlani`, `KentselSit`, `TarihiSit`, `1DereceDogalSit`, `2DereceDogalSit`, `3DereceDogalSit`, `KentselArkeolojikSit`
- `TarimTip`: eklenen `OrganizeTarimVeHayvancilikAlani`; kaldırılan `OrganikTarimVeHayvancilikAlani`
- `YerlesimTip` (yeni liste): `BaglikBahcelik`

**Tanımsız koleksiyon üyeleri:** ['EnerjiDagitimDepolama'] → yok
