"""
Excel导出器 - 将分析结果导出为Excel文件
"""
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
from content_processor import ProcessedContent
from unified_query_chain import QueryResult
import os


class ExcelExporter:
    """Excel导出器"""
    
    def __init__(self, export_config: Dict[str, Any]):
        self.excel_path = export_config.get("excel_path", "output.xlsx")
        self.fields = export_config.get("fields", [
            "url", "title", "snippet", "source_query", "sim", "kw", "fresh", 
            "domain", "structure", "score", "decision", "explanation", 
            "http_status", "depth", "parent", "domain_name", "lang", 
            "render", "content_len", "hash"
        ])
    
    def export_results(self, 
                      contents: List[ProcessedContent],
                      queries: List[QueryResult],
                      demand_text: str,
                      coverage_tags: List[str],
                      task_metadata: Dict[str, Any]) -> str:
        """导出分析结果到Excel"""
        
        # 创建多个工作表
        with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
            # 1. 主要结果工作表
            self._write_results_sheet(writer, contents)
            
            # 2. 查询信息工作表
            self._write_queries_sheet(writer, queries)
            
            # 3. 任务概要工作表
            self._write_summary_sheet(writer, demand_text, coverage_tags, 
                                    contents, queries, task_metadata)
            
            # 4. 统计分析工作表
            self._write_statistics_sheet(writer, contents)
        
        print(f"结果已导出到: {os.path.abspath(self.excel_path)}")
        return self.excel_path
    
    def _write_results_sheet(self, writer: pd.ExcelWriter, contents: List[ProcessedContent]):
        """写入主要结果工作表"""
        if not contents:
            return
        
        # 构建数据行
        data_rows = []
        for content in contents:
            row = {}
            for field in self.fields:
                if field == "url":
                    row[field] = content.url
                elif field == "title":
                    row[field] = content.title
                elif field == "snippet":
                    row[field] = content.snippet
                elif field == "source_query":
                    row[field] = content.source_query
                elif field == "sim":
                    row[field] = round(content.similarity_score, 4)
                elif field == "kw":
                    row[field] = round(content.keyword_score, 4)
                elif field == "fresh":
                    row[field] = round(content.freshness_score, 4)
                elif field == "domain":
                    row[field] = round(content.domain_score, 4)
                elif field == "structure":
                    row[field] = round(content.structure_score, 4)
                elif field == "score":
                    row[field] = round(content.final_score, 4)
                elif field == "decision":
                    row[field] = content.decision
                elif field == "explanation":
                    row[field] = content.explanation
                elif field == "http_status":
                    row[field] = content.http_status
                elif field == "depth":
                    row[field] = content.depth
                elif field == "parent":
                    row[field] = content.parent_url
                elif field == "domain_name":
                    row[field] = content.domain_name
                elif field == "lang":
                    row[field] = content.language
                elif field == "render":
                    row[field] = content.is_rendered
                elif field == "content_len":
                    row[field] = content.content_length
                elif field == "hash":
                    row[field] = content.content_hash[:12]  # 显示前12位
                else:
                    row[field] = ""
            
            data_rows.append(row)
        
        # 创建DataFrame并排序
        df = pd.DataFrame(data_rows)
        df = df.sort_values('score', ascending=False)
        
        # 写入工作表
        df.to_excel(writer, sheet_name='分析结果', index=False)
        
        # 设置列宽
        worksheet = writer.sheets['分析结果']
        for i, column in enumerate(df.columns, 1):
            if column in ['url', 'title', 'explanation']:
                worksheet.column_dimensions[chr(64 + i)].width = 50
            elif column in ['snippet']:
                worksheet.column_dimensions[chr(64 + i)].width = 30
            else:
                worksheet.column_dimensions[chr(64 + i)].width = 12
    
    def _write_queries_sheet(self, writer: pd.ExcelWriter, queries: List[QueryResult]):
        """写入查询信息工作表"""
        if not queries:
            return
        
        query_data = []
        for i, query in enumerate(queries, 1):
            query_data.append({
                '序号': i,
                '查询语句': query.query,
                '生成原因': query.reason,
                '意图标签': query.intent_tag,
                '使用的操作符': ', '.join(query.operators_used)
            })
        
        df = pd.DataFrame(query_data)
        df.to_excel(writer, sheet_name='搜索查询', index=False)
        
        # 设置列宽
        worksheet = writer.sheets['搜索查询']
        worksheet.column_dimensions['A'].width = 8   # 序号
        worksheet.column_dimensions['B'].width = 60  # 查询语句
        worksheet.column_dimensions['C'].width = 40  # 生成原因
        worksheet.column_dimensions['D'].width = 15  # 意图标签
        worksheet.column_dimensions['E'].width = 30  # 使用的操作符
    
    def _write_summary_sheet(self, 
                           writer: pd.ExcelWriter,
                           demand_text: str,
                           coverage_tags: List[str],
                           contents: List[ProcessedContent],
                           queries: List[QueryResult],
                           task_metadata: Dict[str, Any]):
        """写入任务概要工作表"""
        
        # 统计信息
        total_results = len(contents)
        accepted_results = len([c for c in contents if c.decision == 'accepted'])
        avg_score = sum(c.final_score for c in contents) / total_results if total_results > 0 else 0
        high_score_results = len([c for c in contents if c.final_score > 0.7])
        
        # 域名统计
        domain_counts = {}
        for content in contents:
            domain = content.domain_name
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # 构建概要数据
        summary_data = []
        
        # 基本信息
        summary_data.extend([
            ['任务信息', ''],
            ['用户需求', demand_text],
            ['执行时间', task_metadata.get('execution_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))],
            ['配置文件', task_metadata.get('config_path', 'config.yaml')],
            ['', ''],
            
            ['统计信息', ''],
            ['总查询数', len(queries)],
            ['总结果数', total_results],
            ['接受结果数', accepted_results],
            ['平均评分', f"{avg_score:.4f}"],
            ['高分结果数(>0.7)', high_score_results],
            ['', ''],
            
            ['覆盖标签', ''],
        ])
        
        # 添加覆盖标签
        for tag in coverage_tags:
            summary_data.append(['', tag])
        
        summary_data.append(['', ''])
        summary_data.append(['热门域名', ''])
        
        # 添加热门域名
        for domain, count in top_domains:
            summary_data.append(['', f"{domain} ({count}个结果)"])
        
        df_summary = pd.DataFrame(summary_data, columns=['项目', '值'])
        df_summary.to_excel(writer, sheet_name='任务概要', index=False)
        
        # 设置列宽
        worksheet = writer.sheets['任务概要']
        worksheet.column_dimensions['A'].width = 20
        worksheet.column_dimensions['B'].width = 80
    
    def _write_statistics_sheet(self, writer: pd.ExcelWriter, contents: List[ProcessedContent]):
        """写入统计分析工作表"""
        if not contents:
            return
        
        # 评分分布统计
        score_ranges = [
            ('0.0-0.2', 0.0, 0.2),
            ('0.2-0.4', 0.2, 0.4),
            ('0.4-0.6', 0.4, 0.6),
            ('0.6-0.8', 0.6, 0.8),
            ('0.8-1.0', 0.8, 1.0)
        ]
        
        score_distribution = []
        for range_name, min_score, max_score in score_ranges:
            count = len([c for c in contents if min_score <= c.final_score < max_score])
            percentage = count / len(contents) * 100 if contents else 0
            score_distribution.append({
                '评分区间': range_name,
                '数量': count,
                '百分比': f"{percentage:.1f}%"
            })
        
        # 语言分布统计
        lang_counts = {}
        for content in contents:
            lang = content.language
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        
        language_distribution = []
        for lang, count in lang_counts.items():
            percentage = count / len(contents) * 100 if contents else 0
            language_distribution.append({
                '语言': lang,
                '数量': count,
                '百分比': f"{percentage:.1f}%"
            })
        
        # HTTP状态码统计
        status_counts = {}
        for content in contents:
            status = content.http_status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        status_distribution = []
        for status, count in status_counts.items():
            percentage = count / len(contents) * 100 if contents else 0
            status_distribution.append({
                'HTTP状态码': status,
                '数量': count,
                '百分比': f"{percentage:.1f}%"
            })
        
        # 写入统计表格
        start_row = 0
        
        # 评分分布
        df_scores = pd.DataFrame(score_distribution)
        df_scores.to_excel(writer, sheet_name='统计分析', startrow=start_row, index=False)
        start_row += len(df_scores) + 3
        
        # 语言分布
        df_langs = pd.DataFrame(language_distribution)
        df_langs.to_excel(writer, sheet_name='统计分析', startrow=start_row, index=False)
        start_row += len(df_langs) + 3
        
        # HTTP状态码分布
        df_status = pd.DataFrame(status_distribution)
        df_status.to_excel(writer, sheet_name='统计分析', startrow=start_row, index=False)
        
        # 设置列宽
        worksheet = writer.sheets['统计分析']
        worksheet.column_dimensions['A'].width = 15
        worksheet.column_dimensions['B'].width = 12
        worksheet.column_dimensions['C'].width = 12
    
    def create_simple_report(self, contents: List[ProcessedContent], output_path: str = None) -> str:
        """创建简化版本的CSV报告"""
        if output_path is None:
            output_path = self.excel_path.replace('.xlsx', '_simple.csv')
        
        if not contents:
            return output_path
        
        # 选择关键字段
        simple_data = []
        for content in contents:
            simple_data.append({
                'URL': content.url,
                '标题': content.title,
                '评分': round(content.final_score, 4),
                '相似度': round(content.similarity_score, 4),
                '关键词匹配': round(content.keyword_score, 4),
                '域名': content.domain_name,
                '语言': content.language,
                '决策': content.decision,
                '来源查询': content.source_query
            })
        
        df = pd.DataFrame(simple_data)
        df = df.sort_values('评分', ascending=False)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f"简化报告已导出到: {os.path.abspath(output_path)}")
        return output_path