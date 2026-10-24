(async () => {
    const data = JSON.parse(document.getElementById('chart-data').textContent);
    const style = data.style;
    const money = value => new Intl.NumberFormat('en-US', {maximumFractionDigits: data.decimals}).format(value);
    const stamp = value => !Number.isFinite(value) ? '' : new Intl.DateTimeFormat('en-GB', {timeZone: data.timezone, month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false}).format(new Date(value));
    const box = document.getElementById('ohlc');
    const chart = LightweightCharts.createChart(box, {
        width:box.clientWidth, height:box.clientHeight,
        layout:{background:{type:'solid', color:style.panel_background || style.background}, textColor:style.foreground, fontFamily:'Vazirmatn', fontSize:11},
        grid:{vertLines:{color:style.foreground+'0c'}, horzLines:{color:style.foreground+'12'}},
        rightPriceScale:{borderVisible:false, scaleMargins:{top:.15,bottom:.15}},
        timeScale:{borderVisible:false, timeVisible:true, secondsVisible:false, tickMarkFormatter:time=>stamp(time*1000)},
        localization:{priceFormatter:money, timeFormatter:time=>stamp(time*1000)},
        handleScroll:false, handleScale:false,
    });
    const series = chart.addSeries(LightweightCharts.CandlestickSeries, {
        upColor:style.rising,downColor:style.falling,borderVisible:false,
        wickUpColor:style.rising,wickDownColor:style.falling,
        priceLineVisible:false,lastValueVisible:false,
        priceFormat:{type:'price',precision:data.decimals,minMove:10**(-data.decimals)},
    });
    series.setData(data.candles);
    if (data.latest !== null) {
        series.createPriceLine({price:data.latest,color:style.rising,lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dotted,axisLabelVisible:true});
    }
    chart.timeScale().fitContent();
    const lineBox = document.getElementById('line');
    const line = LightweightCharts.createChart(lineBox, {
        width:lineBox.clientWidth, height:lineBox.clientHeight,
        layout:{background:{type:'solid',color:style.panel_background || style.background},textColor:style.foreground,fontFamily:'Vazirmatn',fontSize:11},
        grid:{vertLines:{color:style.foreground+'0c'},horzLines:{color:style.foreground+'12'}},
        rightPriceScale:{borderVisible:false,scaleMargins:{top:.2,bottom:.2}},
        timeScale:{borderVisible:false,timeVisible:true,secondsVisible:false,tickMarkFormatter:time=>stamp(time*1000)},
        localization:{priceFormatter:money,timeFormatter:time=>stamp(time*1000)},
        handleScroll:false,handleScale:false,
    });
    const trend = line.addSeries(LightweightCharts.AreaSeries, {
        lineColor:style.rising,topColor:style.rising+'38',bottomColor:style.rising+'04',
        lineWidth:2,lastValueVisible:false,priceLineVisible:false,
        priceFormat:{type:'price',precision:data.decimals,minMove:10**(-data.decimals)},
        pointMarkersVisible:data.line.filter(point=>point.y!==null).length<4,
    });
    trend.setData(data.line.map(point=>point.y===null?{time:point.x/1000}:{time:point.x/1000,value:point.y}));
    line.timeScale().fitContent();
    if (!data.line.some(point=>point.y!==null)) {
        document.getElementById('empty-line').style.display='flex';
    }
    if (!data.candles.length) {
        document.getElementById('empty-ohlc').style.display='flex';
    }
    await document.fonts.ready;
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    window.chartReady=true;
})();
