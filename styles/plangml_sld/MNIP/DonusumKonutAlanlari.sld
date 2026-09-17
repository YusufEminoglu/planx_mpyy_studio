<?xml version='1.0' encoding='utf-8'?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
	<NamedLayer>
		<Name>MNIP_DONUSUM_KONUT_ALANLARI</Name>
		<UserStyle>
			<Title>MNIP_DONUSUM_KONUT_ALANLARI</Title>
			<FeatureTypeStyle>
				<Rule>
					<Name>0</Name>
					<Title>TOPLU_KONUT_ALANLARI</Title>
					<MaxScaleDenominator>80000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>Donusum</ogc:PropertyName>
							<ogc:Literal>TopluKonutAlanlari</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<GraphicStroke>
								<Graphic>
									<Mark>
										<WellKnownName>ttf://UIP_10_3#0x0052</WellKnownName>
										<Fill>
											<CssParameter name="fill">#FF0000</CssParameter>
										</Fill>
										<Stroke>
											<CssParameter name="stroke-opacity">0</CssParameter>
											<CssParameter name="stroke">#FF0000</CssParameter>
											<CssParameter name="stroke-width">0.3</CssParameter>
										</Stroke>
									</Mark>
									<Size>15</Size>
								</Graphic>
							</GraphicStroke>
							<CssParameter name="stroke-dasharray">10 2</CssParameter>
						</Stroke>
					</LineSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>GECEKONDU_ONLEME_BOLGESI</Title>
					<MaxScaleDenominator>80000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>Donusum</ogc:PropertyName>
							<ogc:Literal>GecekonduOnlemeBolgesi</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<GraphicStroke>
								<Graphic>
									<Mark>
										<WellKnownName>ttf://UIP_10_1#0x0052</WellKnownName>
										<Fill>
											<CssParameter name="fill">#000000</CssParameter>
										</Fill>
										<Stroke>
											<CssParameter name="stroke-opacity">0</CssParameter>
											<CssParameter name="stroke">#000000</CssParameter>
											<CssParameter name="stroke-width">0.3</CssParameter>
										</Stroke>
									</Mark>
									<Size>15</Size>
								</Graphic>
							</GraphicStroke>
							<CssParameter name="stroke-dasharray">10 2</CssParameter>
						</Stroke>
					</LineSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>KENTSEL_DONUSUM_PROJE_ALANLARI</Title>
					<MaxScaleDenominator>80000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>Donusum</ogc:PropertyName>
							<ogc:Literal>KentselDonusumProjeAlani</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<GraphicStroke>
								<Graphic>
									<Mark>
										<WellKnownName>ttf://NIP_10_1#0x0079</WellKnownName>
										<Fill>
											<CssParameter name="fill">#FF0000</CssParameter>
										</Fill>
										<Stroke>
											<CssParameter name="stroke-opacity">0</CssParameter>
											<CssParameter name="stroke">#FF0000</CssParameter>
											<CssParameter name="stroke-width">0.3</CssParameter>
										</Stroke>
									</Mark>
									<Size>15</Size>
								</Graphic>
							</GraphicStroke>
						</Stroke>
					</LineSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>RISKLI_ALAN_SINIRI</Title>
					<MaxScaleDenominator>80000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>Donusum</ogc:PropertyName>
							<ogc:Literal>RiskliAlanSiniri</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<CssParameter name="stroke">#000000</CssParameter>
							<CssParameter name="stroke-width">0.3528</CssParameter>
							<CssParameter name="stroke-dasharray">5 1</CssParameter>
						</Stroke>
					</LineSymbolizer>
					<TextSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Label>RA</Label>
						<Font>
							<CssParameter name="font-family">Calibri</CssParameter>
							<CssParameter name="font-size">5</CssParameter>
							<CssParameter name="font-style">normal</CssParameter>
						</Font>
						<LabelPlacement>
							<LinePlacement>
								<PerpendicularOffset>
       5
    </PerpendicularOffset>
							</LinePlacement>
						</LabelPlacement>
						<Fill>
							<CssParameter name="fill">#000000</CssParameter>
						</Fill>
						<VendorOption name="conflictResolution">false</VendorOption>
						<VendorOption name="repeat">150</VendorOption>
					</TextSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>REZERV_YAPI</Title>
					<MaxScaleDenominator>80000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>Donusum</ogc:PropertyName>
							<ogc:Literal>RezervYapi</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<CssParameter name="stroke">#000000</CssParameter>
							<CssParameter name="stroke-width">0.3528</CssParameter>
							<CssParameter name="stroke-dasharray">5 1</CssParameter>
						</Stroke>
					</LineSymbolizer>
					<TextSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Label>RYA</Label>
						<Font>
							<CssParameter name="font-family">Calibri</CssParameter>
							<CssParameter name="font-size">5</CssParameter>
							<CssParameter name="font-style">normal</CssParameter>
						</Font>
						<LabelPlacement>
							<LinePlacement>
								<PerpendicularOffset>
       5
    </PerpendicularOffset>
							</LinePlacement>
						</LabelPlacement>
						<Fill>
							<CssParameter name="fill">#000000</CssParameter>
						</Fill>
						<VendorOption name="conflictResolution">false</VendorOption>
						<VendorOption name="repeat">150</VendorOption>
					</TextSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>YENILENME_ALAN_SINIRI</Title>
					<MaxScaleDenominator>80000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>Donusum</ogc:PropertyName>
							<ogc:Literal>YenilemeAlanSiniri</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<CssParameter name="stroke">#000000</CssParameter>
							<CssParameter name="stroke-width">0.3528</CssParameter>
							<CssParameter name="stroke-dasharray">5 1</CssParameter>
						</Stroke>
					</LineSymbolizer>
					<TextSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Label>YENİLEME</Label>
						<Font>
							<CssParameter name="font-family">Calibri</CssParameter>
							<CssParameter name="font-size">5</CssParameter>
							<CssParameter name="font-style">normal</CssParameter>
						</Font>
						<LabelPlacement>
							<LinePlacement>
								<PerpendicularOffset>
       5
    </PerpendicularOffset>
							</LinePlacement>
						</LabelPlacement>
						<Fill>
							<CssParameter name="fill">#000000</CssParameter>
						</Fill>
						<VendorOption name="conflictResolution">false</VendorOption>
						<VendorOption name="repeat">150</VendorOption>
					</TextSymbolizer>
				</Rule>
			</FeatureTypeStyle>
		</UserStyle>
	</NamedLayer>
</StyledLayerDescriptor>