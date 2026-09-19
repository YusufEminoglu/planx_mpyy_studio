<?xml version='1.0' encoding='utf-8'?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.0.0" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
	<NamedLayer>
		<Name>MCDP100_ACIK_YESIL_ALAN</Name>
		<UserStyle>
			<Title>CDP_ACIK_YESIL_ALAN</Title>
			<FeatureTypeStyle>
				<Rule>
          <Title>AGACLANDIRILACAK_ALAN</Title>
          <ogc:Filter>
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>YesilTip</ogc:PropertyName>
              <ogc:Literal>AgaclandirilacakAlan</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#62ba52</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke-linejoin">bevel</CssParameter>
            </Stroke>
            <VendorOption name="graphic-margin">-1 -1 26 26</VendorOption>
          </PolygonSymbolizer>
          <PolygonSymbolizer>
            <Fill>
              <GraphicFill>
                <Graphic>
                  <Mark>
                    <WellKnownName>triangle</WellKnownName>
                    <Stroke />
                  </Mark>
                  <Size>11</Size>
                </Graphic>
              </GraphicFill>
            </Fill>
            <Stroke>
              <CssParameter name="stroke-linejoin">bevel</CssParameter>
            </Stroke>
            <VendorOption name="graphic-margin">-1 -1 26 26</VendorOption>
          </PolygonSymbolizer>
          <PointSymbolizer>
            <Graphic>
              <ExternalGraphic>
                <OnlineResource xlink:type="simple" xlink:href="mpyy-eksik-sembol:AgaclandirilacakAlan.svg" />
                <Format>image/svg</Format>
              </ExternalGraphic>
              <Size>38</Size>
            </Graphic>
          </PointSymbolizer>
        </Rule>
			</FeatureTypeStyle>
		</UserStyle>
	</NamedLayer>
</StyledLayerDescriptor>