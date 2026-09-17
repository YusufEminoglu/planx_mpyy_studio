<?xml version='1.0' encoding='utf-8'?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
	<NamedLayer>
		<Name>MUIP_KIYI_YAPILARI</Name>
		<UserStyle>
			<Title>MUIP_KIYI_YAPILARI</Title>
			<FeatureTypeStyle>
				<Rule>
					<Name>0</Name>
					<Title>KONTEYNER_LIMANI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>KonteynerLimani</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:021d4ce1-7fc4-44f4-beaa-7642a693d5aa.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://UIP_10_2#0x0075</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>YAT_LIMANI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>YatLimani</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:833f16d2-e342-473b-8fc2-45a6835fdd22.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://UIP_10_3#0x0051</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>BALIKCI_BARINAGI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>BalikciBarinagi</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:4d1ca539-d61a-4c6d-96a8-be5ebd8c609a.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://uygulama_imar_06_1#0x005f</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>ISKELE</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>Iskele</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:1e5fe38a-0c00-44e4-ae7d-32350098dd83.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://uygulama_imar_07_2#0x0039</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>RIHTIM</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>Rihtim</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:22af0b16-f15d-4261-b5ae-e178ebd7396b.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://uygulama_imar_07_3#0x0036</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>DOLFEN_PLATFORM</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>DolfenPlatform</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:5e3edd1f-02ba-4d4c-9db0-fdc4d349a49b.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://uygulama_imar_07_1#0x006b</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>LIMAN</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>Liman</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:f119e158-b590-4ef5-aa41-63ee49597b17.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://MUIPE_10_2#0x0061</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>TERSANE_ALANI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>TersaneAlani</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:91a1dabf-e01f-4a5a-8e91-c630fe1e4781.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://OG_V_1_2#0x004d</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>KRUVAZIYER_LIMANI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>KruvaziyerLimani</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:23829cd2-7fa0-44ef-a7e6-385063d4409f.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://UIP_10_2#0x0079</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>RO_RO_LIMANI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>RoRoLimani</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:f6d7b23d-fa56-4963-a0dc-447cd3c17e4c.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://UIP_10_3#0x0066</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>TEKNE_IMAL_CEKEK_YERI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>TekneImalCekekYeri</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:01601979-fe87-445c-bdd6-7bf296370a13.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://UIP_10_3#0x0043</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>GEMI_SOKUM_YERI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>GemiSokumYeri</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:29e70ae5-62e2-49c7-ada9-3877ee3acda6.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://UIP_10_1#0x0053</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>BARINAK</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>Barinak</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:405d3a64-0342-42ab-978c-dcd45845b467.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://UIP_10_1#0x0076</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>TEKNE_IMAL_BAKIM_YERI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>TekneImalBakimYeri</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:5329b121-e2e9-41df-89db-c50f8a752397.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://uygulama_imar_07_3#0x0072</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>DENIZ_INIS_RAMPASI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>DenizInisRampasi</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:821b4cde-26a4-4918-baed-6323e4084bbe.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://UIP_10_1#0x0047</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>YAT_LIMANI_BALIKCI_BARINAGI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>YatLimaniBalikciBarinagi</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:985c84b2-3138-40b5-9a09-04ec21d8f686.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://MUIP_10_2#0x0054</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>LIMAN_GERI_HIZMET_ALANI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>LimanGeriHizmetAlani</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:307260f3-9462-4431-b922-c8354253b148.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://MUIPE_10_2#0x0061</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>BALIKCI_BARINAGI_HIZMET_ALANI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>BalikciBarinagiHizmetAlani</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:7d6206ce-14a6-4763-993a-0f1c5e0d77c7.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://UIP_10_1#0x0071</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>DENIZ_OTOBUSU_FERIBOT_ISKELESI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>DenizOtobusuFeribotIskelesi</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:78e341e2-4ffa-4cc4-a97d-fedcc1de362a.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://MUIPE_10_1#0x0072</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>REKREATIF_AMACLI_ISKELE</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>RekreatifAmacliIskele</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:f68571df-e912-4c07-9177-e483bf62fe60.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://MUIPE_10_2#0x0052</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>YUZER_ISKELE</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>YuzerIskele</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:63d1d1d5-8188-434d-be02-c5c96084043e.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://MUIPE_10_3#0x004a</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>YANASMA_YERI</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>YanasmaYeri</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:b1cdf9aa-13ea-42a6-9f62-22ce45ceea70.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://MUIPE_10_3#0x0043</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>SAMANDRA</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>Samandra</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://MUIPE_10_2#0x0031</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>TASFIYE_POMPAJ_ISTASYONU</Title>
					<MaxScaleDenominator>50000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>KiyiYapiTip</ogc:PropertyName>
							<ogc:Literal>TasfiyePompajIstasyonu</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<PolygonSymbolizer>
						<Fill>
							<GraphicFill>
								<Graphic>
									<ExternalGraphic>
										<OnlineResource xlink:type="simple" xlink:href="mpyy-tarama:5ab54191-3b23-42c5-9756-0db79dbf7f4d.png" />
										<Format>image/png</Format>
									</ExternalGraphic>
								</Graphic>
							</GraphicFill>
						</Fill>
					</PolygonSymbolizer>
					<PointSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Graphic>
							<Mark>
								<WellKnownName>ttf://MUIPE_10_2#0x0036</WellKnownName>
								<Fill>
									<CssParameter name="fill">#000000</CssParameter>
								</Fill>
								<Stroke>
									<CssParameter name="stroke-opacity">0</CssParameter>
									<CssParameter name="stroke">#000000</CssParameter>
									<CssParameter name="stroke-width">1</CssParameter>
								</Stroke>
							</Mark>
							<Size>15</Size>
						</Graphic>
					</PointSymbolizer>
				</Rule>
			</FeatureTypeStyle>
		</UserStyle>
	</NamedLayer>
</StyledLayerDescriptor>