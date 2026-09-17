<?xml version='1.0' encoding='utf-8'?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
	<NamedLayer>
		<Name>MUIP_ILETIM_HATTI</Name>
		<UserStyle>
			<Title>MUIP_ILETIM_HATTI</Title>
			<FeatureTypeStyle>
				<Rule>
					<Name>0</Name>
					<Title>BORU_HATTI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>EnerjiHatTip</ogc:PropertyName>
							<ogc:Literal>BoruHatti</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<GraphicStroke>
								<Graphic>
									<Mark>
										<WellKnownName>ttf://OG_V_1_1#0x0077</WellKnownName>
										<Fill>
											<CssParameter name="fill">#000000</CssParameter>
										</Fill>
										<Stroke>
											<CssParameter name="stroke-opacity">0</CssParameter>
											<CssParameter name="stroke">#000000</CssParameter>
											<CssParameter name="stroke-width">0.3</CssParameter>
										</Stroke>
									</Mark>
									<Size>30</Size>
								</Graphic>
							</GraphicStroke>
						</Stroke>
					</LineSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>DOGALGAZ_BORU_HATTI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>EnerjiHatTip</ogc:PropertyName>
							<ogc:Literal>DogalgazBoruHatti</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<GraphicStroke>
								<Graphic>
									<Mark>
										<WellKnownName>ttf://UIP_10_1#0x002a</WellKnownName>
										<Fill>
											<CssParameter name="fill">#000000</CssParameter>
										</Fill>
										<Stroke>
											<CssParameter name="stroke-opacity">0</CssParameter>
											<CssParameter name="stroke">#000000</CssParameter>
											<CssParameter name="stroke-width">0.4</CssParameter>
										</Stroke>
									</Mark>
									<Size>30</Size>
								</Graphic>
							</GraphicStroke>
						</Stroke>
					</LineSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>AKARYAKIT_BORU_HATTI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>EnerjiHatTip</ogc:PropertyName>
							<ogc:Literal>AkaryakitBoruHatti</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<GraphicStroke>
								<Graphic>
									<Mark>
										<WellKnownName>ttf://OG_V_1_1#0x0077</WellKnownName>
										<Fill>
											<CssParameter name="fill">#000000</CssParameter>
										</Fill>
										<Stroke>
											<CssParameter name="stroke-opacity">0</CssParameter>
											<CssParameter name="stroke">#000000</CssParameter>
											<CssParameter name="stroke-width">0.4</CssParameter>
										</Stroke>
									</Mark>
									<Size>30</Size>
								</Graphic>
							</GraphicStroke>
						</Stroke>
					</LineSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>TASIYICI_ILETKEN_BORU_HATTI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>EnerjiHatTip</ogc:PropertyName>
							<ogc:Literal>TasiyiciIletkenBoruHatti</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<GraphicStroke>
								<Graphic>
									<Mark>
										<WellKnownName>ttf://MUIP_10_2#0x002c</WellKnownName>
										<Fill>
											<CssParameter name="fill">#000000</CssParameter>
										</Fill>
										<Stroke>
											<CssParameter name="stroke-opacity">0</CssParameter>
											<CssParameter name="stroke">#000000</CssParameter>
											<CssParameter name="stroke-width">0.4</CssParameter>
										</Stroke>
									</Mark>
									<Size>10</Size>
								</Graphic>
							</GraphicStroke>
						</Stroke>
					</LineSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>ILETIM_KANALI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>EnerjiHatTip</ogc:PropertyName>
							<ogc:Literal>IletimKanali</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<CssParameter name="stroke">#000000</CssParameter>
							<CssParameter name="stroke-width">0.8</CssParameter>
						</Stroke>
					</LineSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>ILETIM_TUNELI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>EnerjiHatTip</ogc:PropertyName>
							<ogc:Literal>IletimTuneli</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<CssParameter name="stroke">#000000</CssParameter>
							<CssParameter name="stroke-width">1</CssParameter>
							<CssParameter name="stroke-dasharray">5 3</CssParameter>
						</Stroke>
					</LineSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>CEBRI_BORU_HATTI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>EnerjiHatTip</ogc:PropertyName>
							<ogc:Literal>CebriBoruHatti</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<CssParameter name="stroke">#000000</CssParameter>
							<CssParameter name="stroke-width">0.8</CssParameter>
						</Stroke>
					</LineSymbolizer>
				</Rule>
			</FeatureTypeStyle>
		</UserStyle>
	</NamedLayer>
</StyledLayerDescriptor>