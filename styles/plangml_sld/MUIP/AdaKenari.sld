<?xml version='1.0' encoding='utf-8'?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
	<NamedLayer>
		<Name>MUIP_ADA_KENARI</Name>
		<UserStyle>
			<Title>MUIP_ADA_KENARI</Title>
			<FeatureTypeStyle>
				<Rule>
					<Name>0</Name>
					<Title>ONERILEN</Title>
					<MaxScaleDenominator>5000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>YolCepheCizgiTip</ogc:PropertyName>
							<ogc:Literal>Onerilen</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<CssParameter name="stroke">#000000</CssParameter>
							<CssParameter name="stroke-width">
								<ogc:PropertyName>YolCepheCizgiTip</ogc:PropertyName>
							</CssParameter>
						</Stroke>
					</LineSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>ONERILEN</Title>
					<MaxScaleDenominator>5000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>YolCepheCizgiTip</ogc:PropertyName>
							<ogc:Literal>Korunan</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<CssParameter name="stroke">#000000</CssParameter>
							<CssParameter name="stroke-width">1</CssParameter>
							<CssParameter name="stroke-dasharray">0.575 0.575</CssParameter>
						</Stroke>
					</LineSymbolizer>
				</Rule>
				<Rule>
					<Name>0</Name>
					<Title>2</Title>
					<MaxScaleDenominator>5000</MaxScaleDenominator>
					<ogc:Filter>
						<ogc:PropertyIsEqualTo>
							<ogc:PropertyName>YolCepheCizgiTip</ogc:PropertyName>
							<ogc:Literal>Duzeltilen</ogc:Literal>
						</ogc:PropertyIsEqualTo>
					</ogc:Filter>
					<LineSymbolizer uom="http://www.opengeospatial.org/se/units/metre">
						<Stroke>
							<CssParameter name="stroke">#000000</CssParameter>
							<CssParameter name="stroke-width">1</CssParameter>
							<CssParameter name="stroke-dasharray">2 0.6</CssParameter>
						</Stroke>
					</LineSymbolizer>
				</Rule>
			</FeatureTypeStyle>
		</UserStyle>
	</NamedLayer>
</StyledLayerDescriptor>