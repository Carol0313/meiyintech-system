/**
 * 中国省市区数据（省级+主要城市）
 */
const CHINA_REGIONS = {
    "北京": ["北京市"], "天津": ["天津市"], "上海": ["上海市"], "重庆": ["重庆市"],
    "河北": ["石家庄", "唐山", "秦皇岛", "邯郸", "邢台", "保定", "张家口", "承德", "沧州", "廊坊", "衡水"],
    "山西": ["太原", "大同", "阳泉", "长治", "晋城", "朔州", "晋中", "运城", "忻州", "临汾", "吕梁"],
    "内蒙古": ["呼和浩特", "包头", "乌海", "赤峰", "通辽", "鄂尔多斯", "呼伦贝尔", "巴彦淖尔", "乌兰察布", "兴安盟", "锡林郭勒", "阿拉善盟"],
    "辽宁": ["沈阳", "大连", "鞍山", "抚顺", "本溪", "丹东", "锦州", "营口", "阜新", "辽阳", "盘锦", "铁岭", "朝阳", "葫芦岛"],
    "吉林": ["长春", "吉林", "四平", "辽源", "通化", "白山", "松原", "白城", "延边"],
    "黑龙江": ["哈尔滨", "齐齐哈尔", "鸡西", "鹤岗", "双鸭山", "大庆", "伊春", "佳木斯", "七台河", "牡丹江", "黑河", "绥化", "大兴安岭"],
    "江苏": ["南京", "苏州", "无锡", "常州", "镇江", "南通", "泰州", "扬州", "盐城", "淮安", "宿迁", "徐州", "连云港"],
    "浙江": ["杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水"],
    "安徽": ["合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城"],
    "福建": ["福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩", "宁德"],
    "江西": ["南昌", "景德镇", "萍乡", "九江", "新余", "鹰潭", "赣州", "吉安", "宜春", "抚州", "上饶"],
    "山东": ["济南", "青岛", "淄博", "枣庄", "东营", "烟台", "潍坊", "济宁", "泰安", "威海", "日照", "莱芜", "临沂", "德州", "聊城", "滨州", "菏泽"],
    "河南": ["郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作", "濮阳", "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店", "济源"],
    "湖北": ["武汉", "黄石", "十堰", "宜昌", "襄阳", "鄂州", "荆门", "孝感", "荆州", "黄冈", "咸宁", "随州", "恩施", "仙桃", "潜江", "天门", "神农架"],
    "湖南": ["长沙", "株洲", "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "益阳", "郴州", "永州", "怀化", "娄底", "湘西"],
    "广东": ["广州", "深圳", "珠海", "汕头", "韶关", "佛山", "江门", "湛江", "茂名", "肇庆", "惠州", "梅州", "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮"],
    "广西": ["南宁", "柳州", "桂林", "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色", "贺州", "河池", "来宾", "崇左"],
    "海南": ["海口", "三亚", "三沙", "儋州", "五指山", "琼海", "文昌", "万宁", "东方", "定安", "屯昌", "澄迈", "临高", "白沙", "昌江", "乐东", "陵水", "保亭", "琼中"],
    "四川": ["成都", "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江", "乐山", "南充", "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳", "阿坝", "甘孜", "凉山"],
    "贵州": ["贵阳", "六盘水", "遵义", "安顺", "毕节", "铜仁", "黔西南", "黔东南", "黔南"],
    "云南": ["昆明", "曲靖", "玉溪", "保山", "昭通", "丽江", "普洱", "临沧", "楚雄", "红河", "文山", "西双版纳", "大理", "德宏", "怒江", "迪庆"],
    "西藏": ["拉萨", "日喀则", "昌都", "林芝", "山南", "那曲", "阿里"],
    "陕西": ["西安", "铜川", "宝鸡", "咸阳", "渭南", "延安", "汉中", "榆林", "安康", "商洛"],
    "甘肃": ["兰州", "嘉峪关", "金昌", "白银", "天水", "武威", "张掖", "平凉", "酒泉", "庆阳", "定西", "陇南", "临夏", "甘南"],
    "青海": ["西宁", "海东", "海北", "黄南", "海南州", "果洛", "玉树", "海西"],
    "宁夏": ["银川", "石嘴山", "吴忠", "固原", "中卫"],
    "新疆": ["乌鲁木齐", "克拉玛依", "吐鲁番", "哈密", "昌吉", "博尔塔拉", "巴音郭楞", "阿克苏", "克孜勒苏", "喀什", "和田", "伊犁", "塔城", "阿勒泰", "石河子", "阿拉尔", "图木舒克", "五家渠", "北屯", "铁门关", "双河", "可克达拉", "昆玉", "胡杨河", "新星"],
    "香港": ["香港特别行政区"], "澳门": ["澳门特别行政区"], "台湾": ["台北", "高雄", "台中", "台南", "基隆", "新竹", "嘉义"]
};

function initRegionSelector(containerId, inputId, selectedRegions) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const selected = {};
    if (selectedRegions) {
        selectedRegions.forEach(r => { selected[r.province] = r.cities || []; });
    }

    let html = '<div class="region-selector">';
    html += '<div class="mb-2"><input type="text" class="form-control region-search" placeholder="搜索省份或城市..." style="border-radius:10px;font-size:0.875rem;"></div>';
    html += '<div class="mb-2 d-flex gap-2">';
    html += '<button type="button" class="btn btn-sm btn-outline-primary" style="border-radius:8px;font-size:0.75rem;" onclick="selectAllRegions(\'' + containerId + '\')">全选</button>';
    html += '<button type="button" class="btn btn-sm btn-outline-secondary" style="border-radius:8px;font-size:0.75rem;" onclick="clearAllRegions(\'' + containerId + '\')">清空</button>';
    html += '</div>';

    html += '<div class="region-grid">';
    Object.keys(CHINA_REGIONS).forEach(province => {
        const cities = CHINA_REGIONS[province];
        const isChecked = selected[province] ? 'checked' : '';
        html += '<div class="region-row" data-province="' + province + '">';
        html += '<div class="region-header">';
        html += '<div class="d-flex align-items-center gap-2">';
        html += '<input class="form-check-input province-check" type="checkbox" id="prov_' + province + '" data-province="' + province + '" ' + isChecked + ' style="width:16px;height:16px;">';
        html += '<label class="form-check-label fw-semibold" for="prov_' + province + '" style="font-size:0.875rem;cursor:pointer;">' + province + '</label>';
        html += '</div>';
        if (cities.length > 1) {
            html += '<button type="button" class="btn btn-link text-muted p-0 region-toggle" data-target="cities_' + province + '" style="font-size:0.75rem;text-decoration:none;"><i class="bi bi-chevron-down"></i></button>';
        }
        html += '</div>';

        if (cities.length > 1) {
            html += '<div class="region-cities" id="cities_' + province + '">';
            cities.forEach(city => {
                const cityChecked = selected[province] && selected[province].includes(city) ? 'checked' : '';
                html += '<div class="form-check form-check-inline" style="margin:0 8px 4px 0;">';
                html += '<input class="form-check-input city-check" type="checkbox" id="city_' + province + '_' + city + '" data-province="' + province + '" data-city="' + city + '" ' + cityChecked + ' style="width:14px;height:14px;">';
                html += '<label class="form-check-label" for="city_' + province + '_' + city + '" style="font-size:0.75rem;cursor:pointer;">' + city + '</label>';
                html += '</div>';
            });
            html += '</div>';
        }
        html += '</div>';
    });
    html += '</div>';

    html += '<div class="region-summary mt-2 p-2 bg-light rounded" style="border-radius:8px;">';
    html += '<div class="small fw-semibold mb-1" style="font-size:0.75rem;">已选区域</div>';
    html += '<div class="region-tags d-flex flex-wrap gap-1"></div>';
    html += '</div>';
    html += '</div>';
    container.innerHTML = html;

    bindRegionEvents(containerId, inputId);
    updateRegionSummary(containerId, inputId);
}

function bindRegionEvents(containerId, inputId) {
    const container = document.getElementById(containerId);

    container.querySelectorAll('.province-check').forEach(cb => {
        cb.addEventListener('change', function() {
            const province = this.dataset.province;
            const cityChecks = container.querySelectorAll('.city-check[data-province="' + province + '"]');
            cityChecks.forEach(c => c.checked = this.checked);
            updateRegionSummary(containerId, inputId);
        });
    });

    container.querySelectorAll('.city-check').forEach(cb => {
        cb.addEventListener('change', function() {
            const province = this.dataset.province;
            const cityChecks = container.querySelectorAll('.city-check[data-province="' + province + '"]');
            const provCheck = container.querySelector('.province-check[data-province="' + province + '"]');
            const allChecked = Array.from(cityChecks).every(c => c.checked);
            const someChecked = Array.from(cityChecks).some(c => c.checked);
            provCheck.checked = allChecked;
            provCheck.indeterminate = someChecked && !allChecked;
            updateRegionSummary(containerId, inputId);
        });
    });

    container.querySelectorAll('.region-toggle').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.getElementById(this.dataset.target);
            if (target.style.display === 'block') {
                target.style.display = 'none';
                this.innerHTML = '<i class="bi bi-chevron-down"></i>';
            } else {
                target.style.display = 'block';
                this.innerHTML = '<i class="bi bi-chevron-up"></i>';
            }
        });
    });

    const searchInput = container.querySelector('.region-search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const term = this.value.trim();
            container.querySelectorAll('.region-row').forEach(row => {
                const province = row.dataset.province;
                const cities = CHINA_REGIONS[province].join(' ');
                const match = province.includes(term) || cities.includes(term);
                row.style.display = match ? 'block' : 'none';
                if (match && term) {
                    const cityDiv = row.querySelector('.region-cities');
                    if (cityDiv) cityDiv.style.display = 'block';
                }
            });
        });
    }
}

function updateRegionSummary(containerId, inputId) {
    const container = document.getElementById(containerId);
    const tagsDiv = container.querySelector('.region-tags');
    const input = document.getElementById(inputId);
    const result = [];
    let tagsHtml = '';

    container.querySelectorAll('.province-check:checked').forEach(provCb => {
        const province = provCb.dataset.province;
        const cityChecks = container.querySelectorAll('.city-check[data-province="' + province + '"]:checked');
        const cities = Array.from(cityChecks).map(c => c.dataset.city);

        if (cities.length === 0 || cities.length === CHINA_REGIONS[province].length) {
            result.push({province: province, cities: []});
            tagsHtml += '<span class="badge bg-primary" style="border-radius:6px;padding:4px 8px;font-size:0.7rem;">' + province + '</span>';
        } else if (cities.length > 0) {
            result.push({province: province, cities: cities});
            tagsHtml += '<span class="badge bg-primary" style="border-radius:6px;padding:4px 8px;font-size:0.7rem;">' + province + ':' + cities.join('、') + '</span>';
        }
    });

    tagsDiv.innerHTML = tagsHtml || '<span class="text-muted small">未选择任何区域</span>';
    if (input) input.value = JSON.stringify(result);
}

function selectAllRegions(containerId) {
    const container = document.getElementById(containerId);
    container.querySelectorAll('.province-check, .city-check').forEach(cb => cb.checked = true);
    container.querySelectorAll('.province-check').forEach(cb => {
        const province = cb.dataset.province;
        const cityDiv = container.querySelector('#cities_' + province);
        if (cityDiv) cityDiv.style.display = 'none';
    });
    const inputId = container.closest('.region-selector')?.querySelector('input[type="hidden"]')?.id || 'serviceRegionsInput';
    updateRegionSummary(containerId, inputId);
}

function clearAllRegions(containerId) {
    const container = document.getElementById(containerId);
    container.querySelectorAll('.province-check, .city-check').forEach(cb => {
        cb.checked = false;
        cb.indeterminate = false;
    });
    const inputId = container.closest('.region-selector')?.querySelector('input[type="hidden"]')?.id || 'serviceRegionsInput';
    updateRegionSummary(containerId, inputId);
}
