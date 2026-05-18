"""
PDF预检工具
自动检测PDF文件的颜色模式、线条粗细、位图等问题
生成检测报告供设计师参考
"""

import fitz
from decimal import Decimal


def preflight_pdf(file_path, min_line_width_mm=0.12):
    """
    PDF预检：检测颜色、线条粗细、位图等问题
    返回检测报告字典
    """
    doc = fitz.open(file_path)
    report = {
        'pages': len(doc),
        'issues': [],
        'warnings': [],
        'ok_items': [],
        'color_stats': {'k100': 0, 'other_k': 0, 'cmy': 0, 'rgb': 0, 'other': 0},
        'line_stats': {'too_thin': 0, 'ok': 0},
        'image_count': 0,
        'text_count': 0,
        'path_count': 0,
    }

    pt_to_mm = 25.4 / 72.0
    min_line_pt = min_line_width_mm / pt_to_mm

    for page_num in range(len(doc)):
        page = doc[page_num]

        # 检测图像
        images = page.get_images()
        report['image_count'] += len(images)
        if images:
            report['warnings'].append(f'第{page_num+1}页包含 {len(images)} 张图片/位图，需注意清晰度')

        # 检测绘制路径（线条）
        drawings = page.get_drawings()
        report['path_count'] += len(drawings)

        for d in drawings:
            # 线条粗细检测
            width = d.get('width', 0)
            if width > 0 and width < min_line_pt:
                report['line_stats']['too_thin'] += 1
                report['issues'].append(
                    f'第{page_num+1}页发现细线条：粗细 {width * pt_to_mm:.3f}mm '
                    f'(低于 {min_line_width_mm}mm 标准)，位置约在 ({d.get("rect", fitz.Rect()).x0:.1f}, {d.get("rect", fitz.Rect()).y0:.1f})'
                )
            elif width > 0:
                report['line_stats']['ok'] += 1

            # 颜色检测
            color = d.get('color')
            fill = d.get('fill')
            for c in [color, fill]:
                if c:
                    result = _analyze_color(c)
                    report['color_stats'][result] += 1

        # 检测文字
        text_blocks = page.get_text('dict')['blocks']
        report['text_count'] += len(text_blocks)

    doc.close()

    # 生成总结
    if report['line_stats']['too_thin'] == 0:
        report['ok_items'].append(f'所有线条粗细均符合 ≥{min_line_width_mm}mm 标准')
    else:
        report['issues'].insert(0, f'共发现 {report["line_stats"]["too_thin"]} 处线条粗细低于 {min_line_width_mm}mm，需要加粗处理')

    if report['image_count'] > 0:
        report['warnings'].append(f'文件中共包含 {report["image_count"]} 张图片/位图，需确认是否为K100%单色黑')
    else:
        report['ok_items'].append('未检测到图片/位图，为纯矢量文件')

    # 颜色总结
    total_colors = sum(report['color_stats'].values())
    if total_colors > 0:
        k100_ratio = report['color_stats']['k100'] / total_colors * 100
        cmy_ratio = report['color_stats']['cmy'] / total_colors * 100
        rgb_ratio = report['color_stats']['rgb'] / total_colors * 100

        if k100_ratio >= 95:
            report['ok_items'].append(f'颜色检测通过：{k100_ratio:.1f}% 为单色K100%')
        else:
            report['issues'].insert(0, f'颜色检测不通过：仅 {k100_ratio:.1f}% 为K100%，{cmy_ratio:.1f}%含CMY色，{rgb_ratio:.1f}%为RGB色，需转单色黑')

    report['pass'] = len(report['issues']) == 0
    return report


def _analyze_color(color):
    """分析颜色类型"""
    if not color:
        return 'other'

    if len(color) >= 3:
        r, g, b = color[0], color[1], color[2]
        # 判断是否为RGB中的单色黑 (0,0,0)
        if r == 0 and g == 0 and b == 0:
            return 'k100'
        # 判断是否为RGB中的灰度（近似K）
        if abs(r - g) < 0.05 and abs(g - b) < 0.05:
            if r > 0.9:
                return 'other_k'
            else:
                return 'k100'
        # 判断是否为纯RGB（不含K通道信息）
        return 'rgb'

    if len(color) == 4:
        # CMYK
        c, m, y, k = color[0], color[1], color[2], color[3]
        if c == 0 and m == 0 and y == 0 and k == 1:
            return 'k100'
        if c == 0 and m == 0 and y == 0:
            return 'other_k'
        if c > 0 or m > 0 or y > 0:
            return 'cmy'
        return 'other'

    if len(color) == 1:
        # Gray
        if color[0] == 0:
            return 'k100'
        return 'other_k'

    return 'other'


def generate_preflight_report_html(report):
    """生成预检报告的HTML片段"""
    status = '通过' if report['pass'] else '不通过'
    status_color = '#10b981' if report['pass'] else '#ef4444'

    html = f'''
    <div class="preflight-report" style="border:1px solid #e2e8f0; border-radius:12px; overflow:hidden;">
        <div style="padding:12px 16px; background:{status_color}; color:white; font-weight:600; display:flex; justify-content:space-between; align-items:center;">
            <span><i class="bi bi-clipboard-check"></i> PDF预检报告</span>
            <span>{status}</span>
        </div>
        <div style="padding:16px;">
    '''

    if report['issues']:
        html += '<div style="margin-bottom:12px;"><div style="font-weight:600; color:#ef4444; margin-bottom:6px;"><i class="bi bi-x-circle"></i> 问题（必须处理）</div>'
        for issue in report['issues']:
            html += f'<div style="padding:6px 10px; background:#fef2f2; border-radius:6px; margin-bottom:4px; font-size:0.8125rem; color:#991b1b;">• {issue}</div>'
        html += '</div>'

    if report['warnings']:
        html += '<div style="margin-bottom:12px;"><div style="font-weight:600; color:#f59e0b; margin-bottom:6px;"><i class="bi bi-exclamation-triangle"></i> 警告（建议检查）</div>'
        for warning in report['warnings']:
            html += f'<div style="padding:6px 10px; background:#fffbeb; border-radius:6px; margin-bottom:4px; font-size:0.8125rem; color:#92400e;">• {warning}</div>'
        html += '</div>'

    if report['ok_items']:
        html += '<div style="margin-bottom:12px;"><div style="font-weight:600; color:#10b981; margin-bottom:6px;"><i class="bi bi-check-circle"></i> 通过项</div>'
        for item in report['ok_items']:
            html += f'<div style="padding:6px 10px; background:#f0fdf4; border-radius:6px; margin-bottom:4px; font-size:0.8125rem; color:#166534;">✓ {item}</div>'
        html += '</div>'

    html += f'''
            <div style="display:flex; gap:16px; margin-top:12px; padding-top:12px; border-top:1px solid #e2e8f0; font-size:0.75rem; color:#64748b;">
                <span>页数: {report['pages']}</span>
                <span>路径: {report['path_count']}</span>
                <span>图片: {report['image_count']}</span>
                <span>文字块: {report['text_count']}</span>
            </div>
        </div>
    </div>
    '''
    return html
