# utils/pdf_generator.py

import io
import base64
from datetime import datetime
from typing import Optional
import re

try:
    import markdown
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from bs4 import BeautifulSoup
    import urllib.request
    import os
    import platform
    PDF_LIBS_AVAILABLE = True
except ImportError as e:
    print(f"PDF 라이브러리 import 오류: {e}")
    PDF_LIBS_AVAILABLE = False
    
try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    # 로거가 없어도 작동하도록
    import logging
    logger = logging.getLogger(__name__)

class MarkdownToPDFConverter:
    """마크다운 텍스트를 예쁜 PDF로 변환하는 클래스"""
    
    def __init__(self):
        if not PDF_LIBS_AVAILABLE:
            raise ImportError("PDF 생성에 필요한 라이브러리들이 설치되지 않았습니다. requirements.txt의 PDF Generation 섹션을 확인하세요.")
        
        # 한글 폰트 설정
        self.korean_font = self._setup_korean_font()
        
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_korean_font(self):
        """한글 폰트 설정"""
        try:
            # 먼저 이미 등록된 폰트가 있는지 확인
            try:
                # 기존에 등록된 KoreanFont가 있는지 확인
                from reportlab.pdfbase import pdfmetrics
                pdfmetrics.getFont('KoreanFont')
                logger.info("기존 등록된 한글 폰트 사용")
                return 'KoreanFont'
            except:
                pass
            
            # 시스템별 기본 한글 폰트 경로
            font_paths = []
            
            if platform.system() == "Windows":
                font_paths = [
                    "C:/Windows/Fonts/malgun.ttf",  # 맑은 고딕
                    "C:/Windows/Fonts/gulim.ttc",   # 굴림
                    "C:/Windows/Fonts/dotum.ttc",   # 돋움
                ]
            elif platform.system() == "Darwin":  # macOS
                font_paths = [
                    "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # 애플 SD 고딕 Neo
                    "/Library/Fonts/AppleGothic.ttf",  # 애플고딕
                ]
            else:  # Linux
                font_paths = [
                    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # 나눔고딕
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # DejaVu Sans
                ]
            
            # 폰트 파일을 찾아서 등록
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('KoreanFont', font_path))
                        logger.info(f"한글 폰트 등록 성공: {font_path}")
                        return 'KoreanFont'
                    except Exception as e:
                        logger.warning(f"폰트 등록 실패 {font_path}: {str(e)}")
                        continue
            
            # 웹에서 나눔고딕 다운로드 시도 (리눅스/도커 환경)
            try:
                font_url = "https://github.com/naver/nanumfont/raw/master/fonts/NanumGothic.ttf"
                font_dir = os.path.expanduser("~/.local/share/fonts/")
                os.makedirs(font_dir, exist_ok=True)
                font_path = os.path.join(font_dir, "NanumGothic.ttf")
                
                if not os.path.exists(font_path):
                    logger.info("나눔고딕 폰트 다운로드 시작...")
                    urllib.request.urlretrieve(font_url, font_path)
                    logger.info("나눔고딕 폰트 다운로드 완료")
                
                pdfmetrics.registerFont(TTFont('KoreanFont', font_path))
                logger.info(f"웹 다운로드 한글 폰트 등록 성공: {font_path}")
                return 'KoreanFont'
                
            except Exception as e:
                logger.warning(f"웹 폰트 다운로드 실패: {str(e)}")
            
            # 모든 한글 폰트 설정 실패시 기본 폰트 사용
            logger.warning("한글 폰트 설정 실패, 기본 폰트 사용")
            return 'Helvetica'
            
        except Exception as e:
            logger.error(f"한글 폰트 설정 오류: {str(e)}")
            return 'Helvetica'
        
    def _setup_custom_styles(self):
        """전문적이고 매력적인 PDF 스타일 설정"""
        bold_font = self.korean_font if self.korean_font == 'KoreanFont' else 'Helvetica-Bold'
        
        # 메인 제목 스타일 (깔끔하고 일관된)
        self.styles.add(ParagraphStyle(
            name='CustomH1',
            parent=self.styles['Heading1'],
            fontSize=20,
            spaceAfter=15,
            spaceBefore=15,
            textColor=HexColor('#2563eb'),  # 전문적 파란색
            fontName=bold_font,
            alignment=TA_LEFT,
            borderWidth=0,  # 테두리 제거
            borderPadding=0,
            backColor=None  # 배경색 제거
        ))
        
        # 섹션 제목 스타일 (간결한 녹색)
        self.styles.add(ParagraphStyle(
            name='CustomH2',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=18,
            textColor=HexColor('#059669'),  # 녹색
            fontName=bold_font,
            leftIndent=0,  # 들여쓰기 제거
            borderWidth=0,  # 테두리 제거
            borderPadding=0,
            backColor=None  # 배경색 제거
        ))
        
        # 서브 섹션 제목 스타일 (간결한 주황색)
        self.styles.add(ParagraphStyle(
            name='CustomH3',
            parent=self.styles['Heading3'],
            fontSize=14,
            spaceAfter=10,
            spaceBefore=14,
            textColor=HexColor('#d97706'),  # 주황색
            fontName=bold_font,
            leftIndent=0,
            borderWidth=0,  # 테두리 제거
            borderPadding=0,
            backColor=None  # 배경색 제거
        ))
        
        # 본문 스타일 (최적 가독성)
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            spaceBefore=3,
            leading=16,
            textColor=HexColor('#374151'),
            fontName=self.korean_font,
            alignment=TA_LEFT,
            leftIndent=0,
            rightIndent=0
        ))
        
        # 강조 텍스트 스타일 (깔끔한 강조)
        self.styles.add(ParagraphStyle(
            name='CustomEmphasis',
            parent=self.styles['CustomBody'],
            fontSize=11,
            textColor=HexColor('#1f2937'),  # 진한 회색
            fontName=bold_font,
            spaceBefore=4,
            spaceAfter=4,
            backColor=None,  # 배경색 제거
            borderPadding=0,
            borderWidth=0  # 테두리 제거
        ))
        
        # 리스트 스타일 (깔끔한 들여쓰기)
        self.styles.add(ParagraphStyle(
            name='CustomList',
            parent=self.styles['Normal'],
            fontSize=11,
            leftIndent=20,
            spaceAfter=4,
            spaceBefore=2,
            bulletIndent=10,
            textColor=HexColor('#374151'),
            fontName=self.korean_font,
            leading=16,
            backColor=None,  # 배경색 제거
            borderPadding=0
        ))
        
        # 인용문 스타일 (간결한 들여쓰기)
        self.styles.add(ParagraphStyle(
            name='CustomQuote',
            parent=self.styles['Normal'],
            fontSize=11,
            leftIndent=20,
            rightIndent=20,
            spaceAfter=8,
            spaceBefore=8,
            textColor=HexColor('#6b7280'),
            fontName=self.korean_font,
            leading=16,
            borderWidth=0,  # 테두리 제거
            borderPadding=0,
            backColor=None  # 배경색 제거
        ))
        
        # 성공 메시지 스타일 (가독성 중심)
        self.styles.add(ParagraphStyle(
            name='SuccessStyle',
            parent=self.styles['CustomBody'],
            fontSize=11,
            textColor=HexColor('#059669'),
            fontName=self.korean_font,
            spaceBefore=6,
            spaceAfter=6,
            backColor=HexColor('#f0fdf4'),  # 연한 배경
            borderPadding=8,
            borderWidth=1,
            borderColor=HexColor('#bbf7d0')  # 연한 테두리
        ))
        
        # 경고/오류 메시지 스타일 (가독성 중심)
        self.styles.add(ParagraphStyle(
            name='WarningStyle',
            parent=self.styles['CustomBody'],
            fontSize=11,
            textColor=HexColor('#dc2626'),
            fontName=self.korean_font,
            spaceBefore=6,
            spaceAfter=6,
            backColor=HexColor('#fef2f2'),  # 연한 배경
            borderPadding=8,
            borderWidth=1,
            borderColor=HexColor('#fecaca')  # 연한 테두리
        ))

    def convert_markdown_to_pdf(self, markdown_text: str, filename: Optional[str] = None) -> bytes:
        """마크다운 텍스트를 PDF 바이트로 변환"""
        try:
            logger.info("마크다운을 PDF로 변환 시작")
            
            # 파일명 자동 생성
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"agentic_rag_report_{timestamp}.pdf"
            
            # PDF 생성을 위한 메모리 버퍼
            buffer = io.BytesIO()
            
            # PDF 문서 생성
            doc = SimpleDocTemplate(
                buffer, 
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # 스토리 (PDF 내용) 생성
            story = []
            
            # 깔끔한 표지 디자인
            title_style = ParagraphStyle(
                'TitleStyle',
                parent=self.styles['CustomH1'],
                fontName=self.korean_font,
                fontSize=24,  # 적당한 크기
                textColor=HexColor('#2563eb'),
                alignment=TA_CENTER,
                spaceAfter=16,
                spaceBefore=12,
                borderWidth=0,  # 테두리 제거
                borderPadding=0,
                backColor=None  # 배경색 제거
            )
            
            story.append(Paragraph("📊 시너지 보고서", title_style))
            
            # 바제목 (간결한 스타일)
            subtitle_style = ParagraphStyle(
                'SubtitleStyle',
                parent=self.styles['Normal'],
                fontName=self.korean_font,
                fontSize=14,
                textColor=HexColor('#6b7280'),
                alignment=TA_CENTER,
                spaceAfter=20,
                spaceBefore=8,
                borderWidth=0,  # 테두리 제거
                borderPadding=0,
                backColor=None  # 배경색 제거
            )
            story.append(Paragraph("지능형 데이터 분석 결과", subtitle_style))
            
            # 생성 정보 (간결한 텍스트)
            info_style = ParagraphStyle(
                'InfoStyle',
                parent=self.styles['Normal'],
                fontName=self.korean_font,
                fontSize=10,
                textColor=HexColor('#6b7280'),
                alignment=TA_CENTER,
                spaceAfter=20
            )
            story.append(Paragraph(f"생성 시간: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')}", info_style))
            
            # 간결한 구분선
            divider_style = ParagraphStyle(
                'DividerStyle',
                parent=self.styles['Normal'],
                alignment=TA_CENTER,
                textColor=HexColor('#d1d5db'),
                fontSize=12,
                spaceBefore=10,
                spaceAfter=10
            )
            story.append(Paragraph("─" * 50, divider_style))
            story.append(Spacer(1, 15))
            
            # 마크다운 파싱 및 PDF 요소 변환
            self._parse_markdown_to_story(markdown_text, story)
            
            # 간결한 푸터
            story.append(Spacer(1, 25))
            
            # 간단한 구분선
            story.append(Paragraph("─" * 50, divider_style))
            story.append(Spacer(1, 12))
            
            # 저작권 정보 (깔끔하게)
            footer_style = ParagraphStyle(
                'FooterStyle', 
                parent=self.styles['Normal'],
                fontName=self.korean_font,
                fontSize=9,
                textColor=HexColor('#9ca3af'),
                alignment=TA_CENTER
            )
            story.append(Paragraph(f"시너지 AI 시스템 · {datetime.now().strftime('%Y')}", footer_style))
            
            # PDF 빌드
            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info(f"PDF 변환 완료: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"PDF 변환 중 오류 발생: {str(e)}")
            raise e

    def _parse_markdown_to_story(self, markdown_text: str, story: list):
        """마크다운 텍스트를 PDF 스토리 요소로 변환"""
        try:
            # HTML로 변환 후 파싱
            html = markdown.markdown(markdown_text, extensions=['tables'])
            soup = BeautifulSoup(html, 'html.parser')
            
            for element in soup.find_all(['h1', 'h2', 'h3', 'p', 'ul', 'ol', 'table', 'hr']):
                if element.name in ['h1', 'h2']:
                    # 제목 처리
                    text = element.get_text().strip()
                    if element.name == 'h1':
                        story.append(Paragraph(text, self.styles['CustomH1']))
                    else:
                        story.append(Paragraph(text, self.styles['CustomH2']))
                    story.append(Spacer(1, 6))
                    
                elif element.name == 'h3':
                    # 3차 제목 처리
                    text = element.get_text().strip()
                    story.append(Paragraph(text, self.styles['CustomH3']))
                    story.append(Spacer(1, 8))
                    
                elif element.name == 'p':
                    # 문단 처리 (한글 폰트 확실히 적용)
                    text = element.get_text().strip()
                    if text:
                        # 강조 텍스트 감지 및 스타일 적용
                        if text.startswith('**') and text.endswith('**'):
                            # 강조 텍스트
                            clean_text = text.strip('*')
                            story.append(Paragraph(f"<b>{clean_text}</b>", self.styles['CustomEmphasis']))
                        elif '❌' in text or '⚠️' in text or '오류' in text or '작동하지 않음' in text or '연결이 필요' in text:
                            # 오류/경고 텍스트 (기존 정의된 스타일 사용)
                            story.append(Paragraph(f"🚨 {text}", self.styles['WarningStyle']))
                        elif '✅' in text or '성공' in text or '완료' in text or '정상' in text:
                            # 성공 텍스트 (기존 정의된 스타일 사용)
                            story.append(Paragraph(f"✨ {text}", self.styles['SuccessStyle']))
                        else:
                            # 일반 텍스트
                            story.append(Paragraph(text, self.styles['CustomBody']))
                        story.append(Spacer(1, 4))
                        
                elif element.name in ['ul', 'ol']:
                    # 리스트 처리 (한글 폰트 확실히 적용)
                    list_items = element.find_all('li')
                    for i, li in enumerate(list_items):
                        text = li.get_text().strip()
                        if element.name == 'ol':
                            # 순서가 있는 리스트
                            bullet = f"{i+1}."
                        else:
                            # 불릿 리스트 (다양한 스타일)
                            if i % 3 == 0:
                                bullet = "●"
                            elif i % 3 == 1:
                                bullet = "○"
                            else:
                                bullet = "▶"
                        
                        list_para = Paragraph(f"{bullet} {text}", self.styles['CustomList'])
                        story.append(list_para)
                    story.append(Spacer(1, 10))
                    
                elif element.name == 'table':
                    # 테이블 처리
                    self._add_table_to_story(element, story)
                    
                elif element.name == 'hr':
                    # 간단한 구분선
                    story.append(Spacer(1, 12))
                    hr_style = ParagraphStyle(
                        'HRStyle',
                        parent=self.styles['Normal'],
                        alignment=TA_CENTER,
                        textColor=HexColor('#d1d5db'),
                        fontSize=12
                    )
                    story.append(Paragraph("─" * 40, hr_style))
                    story.append(Spacer(1, 12))
                    
        except Exception as e:
            logger.error(f"마크다운 파싱 오류: {str(e)}")
            # 파싱 실패시 원문 그대로 추가
            story.append(Paragraph("원본 텍스트:", self.styles['CustomH2']))
            story.append(Paragraph(markdown_text.replace('\n', '<br/>'), self.styles['CustomBody']))

    def _add_table_to_story(self, table_element, story: list):
        """HTML 테이블을 PDF 테이블로 변환하여 스토리에 추가"""
        try:
            rows = []
            
            # 헤더 처리
            thead = table_element.find('thead')
            if thead:
                header_row = []
                for th in thead.find_all('th'):
                    header_row.append(th.get_text().strip())
                rows.append(header_row)
            
            # 본문 처리
            tbody = table_element.find('tbody') or table_element
            for tr in tbody.find_all('tr'):
                row = []
                for td in tr.find_all(['td', 'th']):
                    row.append(td.get_text().strip())
                if row:
                    rows.append(row)
            
            if rows:
                # 테이블 생성
                table = Table(rows)
                # 한글 폰트 설정
                header_font = self.korean_font if self.korean_font == 'KoreanFont' else 'Helvetica-Bold'
                body_font = self.korean_font if self.korean_font == 'KoreanFont' else 'Helvetica'
                
                table.setStyle(TableStyle([
                    # 헤더 스타일 (더 매력적인 색상과 디자인)
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3b82f6')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), header_font),
                    ('FONTSIZE', (0, 0), (-1, 0), 13),
                    
                    # 본문 스타일 (교대로 배경색 적용)
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('TEXTCOLOR', (0, 1), (-1, -1), HexColor('#374151')),
                    ('FONTNAME', (0, 1), (-1, -1), body_font),
                    ('FONTSIZE', (0, 1), (-1, -1), 11),
                    
                    # 행 교대 배경색 (더 보기 좋게)
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8fafc')]),
                    
                    # 테두리 (더 세련된 스타일)
                    ('GRID', (0, 0), (-1, -1), 1.5, HexColor('#cbd5e1')),
                    ('BOX', (0, 0), (-1, -1), 2, HexColor('#64748b')),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    
                    # 패딩 (더 여유있게)
                    ('LEFTPADDING', (0, 0), (-1, -1), 15),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 15),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ]))
                
                story.append(Spacer(1, 12))
                story.append(table)
                story.append(Spacer(1, 12))
                
        except Exception as e:
            logger.error(f"테이블 변환 오류: {str(e)}")

def create_pdf_download_link(pdf_bytes: bytes, filename: str) -> str:
    """PDF 바이트를 다운로드 링크로 변환"""
    b64_pdf = base64.b64encode(pdf_bytes).decode()
    return f'<a href="data:application/octet-stream;base64,{b64_pdf}" download="{filename}">📄 PDF 다운로드</a>'

def get_pdf_download_button_html(pdf_bytes: bytes, filename: str) -> str:
    """PDF 다운로드를 위한 HTML 버튼 생성"""
    b64_pdf = base64.b64encode(pdf_bytes).decode()
    button_html = f'''
    <div style="text-align: center; margin: 20px 0;">
        <a href="data:application/pdf;base64,{b64_pdf}" 
           download="{filename}"
           style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                  color: white;
                  padding: 12px 24px;
                  border-radius: 8px;
                  text-decoration: none;
                  font-weight: bold;
                  font-size: 16px;
                  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
                  display: inline-block;
                  transition: transform 0.2s;"
           onmouseover="this.style.transform='translateY(-2px)'"
           onmouseout="this.style.transform='translateY(0)'">
            📄 PDF로 저장하기
        </a>
    </div>
    '''
    return button_html

def get_text_download_button_html(text_content: str, filename: str) -> str:
    """텍스트 다운로드를 위한 HTML 버튼 생성 (PDF 대안)"""
    text_bytes = text_content.encode('utf-8')
    b64_text = base64.b64encode(text_bytes).decode()
    button_html = f'''
    <div style="text-align: center; margin: 20px 0;">
        <a href="data:text/plain;base64,{b64_text}" 
           download="{filename}"
           style="background: #6b7280;
                  color: white;
                  padding: 10px 20px;
                  border-radius: 6px;
                  text-decoration: none;
                  font-size: 14px;
                  display: inline-block;
                  transition: background 0.2s;"
           onmouseover="this.style.background='#4b5563'"
           onmouseout="this.style.background='#6b7280'">
            📝 텍스트로 저장하기
        </a>
        <div style="margin-top: 8px; font-size: 12px; color: #6b7280;">
            PDF 기능을 위해 필요한 라이브러리 설치: pip install markdown reportlab beautifulsoup4
        </div>
    </div>
    '''
    return button_html

def is_pdf_available() -> bool:
    """PDF 생성 기능이 사용 가능한지 확인"""
    return PDF_LIBS_AVAILABLE