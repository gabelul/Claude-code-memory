"""HTML report generator for Claude Code conversations with GPT analysis."""

import html
import re
from pathlib import Path
from typing import Union, Optional
from datetime import datetime

from .parser import ChatParser, ChatConversation
from .summarizer import ChatSummarizer, SummaryResult


class ChatHtmlReporter:
    """Generates HTML reports combining GPT analysis with conversation display."""
    
    def __init__(self, config=None):
        """Initialize reporter with chat parser and summarizer."""
        self.parser = ChatParser()
        self.summarizer = ChatSummarizer(config)
    
    def generate_report(self, conversation_input: Union[str, Path, ChatConversation],
                       output_path: Optional[Path] = None) -> Path:
        """Generate HTML report for a conversation.
        
        Args:
            conversation_input: Conversation ID, chat file path, or ChatConversation object
            output_path: Where to save HTML file (auto-generated if None)
            
        Returns:
            Path to generated HTML file
        """
        # Parse conversation if needed
        if isinstance(conversation_input, ChatConversation):
            conversation = conversation_input
        else:
            conversation = self._load_conversation(conversation_input)
        
        if not conversation:
            raise ValueError(f"Could not load conversation from: {conversation_input}")
        
        # Generate GPT summary
        summary_result = self.summarizer.summarize_conversation(conversation)
        
        # Generate HTML content
        html_content = self._generate_html(conversation, summary_result)
        
        # Determine output path
        if output_path is None:
            output_path = self._generate_output_path(conversation)
        
        # Write HTML file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
    def _load_conversation(self, conversation_input: Union[str, Path]) -> Optional[ChatConversation]:
        """Load conversation from ID or file path."""
        input_path = Path(conversation_input)
        
        if input_path.exists() and input_path.suffix == '.jsonl':
            # Direct file path
            return self.parser.parse_jsonl(input_path)
        
        # Try to find by conversation ID or project path
        try:
            if input_path.is_absolute():
                # Project path - get most recent chat
                chat_files = self.parser.get_chat_files(input_path)
                if chat_files:
                    return self.parser.parse_jsonl(chat_files[0])
            else:
                # Could be a conversation ID - search for it
                # For now, treat as relative path
                if input_path.exists():
                    return self.parser.parse_jsonl(input_path)
        except Exception:
            pass
        
        return None
    
    def _generate_output_path(self, conversation: ChatConversation) -> Path:
        """Generate output path for HTML report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_report_{conversation.metadata.session_id}_{timestamp}.html"
        reports_dir = Path.cwd() / "chat_reports"
        reports_dir.mkdir(exist_ok=True)
        return reports_dir / filename
    
    def _generate_html(self, conversation: ChatConversation, summary: SummaryResult) -> str:
        """Generate complete HTML content."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat Report - {html.escape(conversation.metadata.session_id)}</title>
    <style>
        {self._get_css_styles()}
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet">
</head>
<body>
    <div class="container">
        {self._generate_header(conversation)}
        {self._generate_summary_section(summary)}
        {self._generate_conversation_section(conversation)}
    </div>
    
    <script>
        {self._get_javascript()}
    </script>
</body>
</html>"""
    
    def _get_css_styles(self) -> str:
        """Get CSS styles for the HTML report."""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .header h1 {
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 2.2em;
        }
        
        .metadata {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .metadata-item {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
        }
        
        .metadata-label {
            font-weight: 600;
            color: #2c3e50;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .metadata-value {
            color: #34495e;
            font-size: 1.1em;
            margin-top: 5px;
        }
        
        .summary-section {
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .section-title {
            font-size: 1.8em;
            color: #2c3e50;
            margin-bottom: 20px;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
        }
        
        .summary-card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            border-left: 4px solid #e74c3c;
        }
        
        .summary-card.insights {
            border-left-color: #f39c12;
        }
        
        .summary-card.topics {
            border-left-color: #27ae60;
        }
        
        .summary-card.patterns {
            border-left-color: #9b59b6;
        }
        
        .summary-card h3 {
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 1.2em;
        }
        
        .summary-text {
            color: #34495e;
            line-height: 1.7;
        }
        
        .tag-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        
        .tag {
            background: #3498db;
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
        }
        
        .tag.insight { background: #f39c12; }
        .tag.topic { background: #27ae60; }
        .tag.pattern { background: #9b59b6; }
        
        .conversation-section {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .conversation-header {
            background: #34495e;
            color: white;
            padding: 20px;
        }
        
        .conversation-header h2 {
            font-size: 1.6em;
        }
        
        .message {
            border-bottom: 1px solid #ecf0f1;
            padding: 25px;
        }
        
        .message:last-child {
            border-bottom: none;
        }
        
        .message.user {
            background: #f8f9fa;
        }
        
        .message.assistant {
            background: white;
        }
        
        .message-header {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .role-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .role-badge.user {
            background: #3498db;
            color: white;
        }
        
        .role-badge.assistant {
            background: #27ae60;
            color: white;
        }
        
        .message-timestamp {
            margin-left: auto;
            color: #7f8c8d;
            font-size: 0.9em;
        }
        
        .message-content {
            color: #2c3e50;
            line-height: 1.7;
        }
        
        .message-content h1,
        .message-content h2,
        .message-content h3,
        .message-content h4,
        .message-content h5,
        .message-content h6 {
            margin: 20px 0 10px 0;
            color: #2c3e50;
        }
        
        .message-content p {
            margin-bottom: 15px;
        }
        
        .message-content ul,
        .message-content ol {
            margin: 15px 0;
            padding-left: 25px;
        }
        
        .message-content li {
            margin-bottom: 5px;
        }
        
        .message-content code {
            background: #f1f2f6;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
            font-size: 0.9em;
        }
        
        .message-content pre {
            background: #2d3748;
            color: #e2e8f0;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 15px 0;
            font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
            line-height: 1.5;
        }
        
        .message-content pre code {
            background: none;
            padding: 0;
            color: inherit;
            font-size: 0.9em;
        }
        
        .message-content blockquote {
            border-left: 4px solid #3498db;
            margin: 15px 0;
            padding: 15px 20px;
            background: #f8f9fa;
            font-style: italic;
        }
        
        .stats-bar {
            background: #ecf0f1;
            padding: 15px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9em;
            color: #7f8c8d;
        }
        
        .word-count {
            font-weight: 600;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .metadata {
                grid-template-columns: 1fr;
            }
            
            .summary-grid {
                grid-template-columns: 1fr;
            }
            
            .message-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }
            
            .message-timestamp {
                margin-left: 0;
            }
        }
        
        /* Scroll to top button */
        .scroll-top {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            cursor: pointer;
            font-size: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            transition: background 0.3s;
            display: none;
        }
        
        .scroll-top:hover {
            background: #2980b9;
        }
        
        .scroll-top.visible {
            display: block;
        }
        """
    
    def _generate_header(self, conversation: ChatConversation) -> str:
        """Generate header section with metadata."""
        metadata = conversation.metadata
        
        return f"""
        <div class="header">
            <h1>Claude Code Chat Report</h1>
            <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
            
            <div class="metadata">
                <div class="metadata-item">
                    <div class="metadata-label">Session ID</div>
                    <div class="metadata-value">{html.escape(metadata.session_id)}</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Project Path</div>
                    <div class="metadata-value">{html.escape(metadata.project_path)}</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Duration</div>
                    <div class="metadata-value">{metadata.duration_minutes:.1f} minutes</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Messages</div>
                    <div class="metadata-value">{metadata.message_count} messages</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Total Words</div>
                    <div class="metadata-value">{metadata.total_words:,} words</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Contains Code</div>
                    <div class="metadata-value">{'Yes' if metadata.has_code else 'No'}</div>
                </div>
                {f'''<div class="metadata-item">
                    <div class="metadata-label">Primary Language</div>
                    <div class="metadata-value">{html.escape(metadata.primary_language)}</div>
                </div>''' if metadata.primary_language else ''}
            </div>
        </div>
        """
    
    def _generate_summary_section(self, summary: SummaryResult) -> str:
        """Generate GPT analysis summary section."""
        return f"""
        <div class="summary-section">
            <h2 class="section-title">GPT Analysis Summary</h2>
            
            <div class="summary-grid">
                <div class="summary-card">
                    <h3>Summary</h3>
                    <div class="summary-text">{html.escape(summary.summary)}</div>
                    {f'<div class="tag-list"><span class="tag">{html.escape(summary.category)}</span></div>' if summary.category else ''}
                </div>
                
                {f'''<div class="summary-card insights">
                    <h3>Key Insights</h3>
                    <div class="tag-list">
                        {' '.join(f'<span class="tag insight">{html.escape(insight)}</span>' for insight in summary.key_insights)}
                    </div>
                </div>''' if summary.key_insights else ''}
                
                {f'''<div class="summary-card topics">
                    <h3>Topics Discussed</h3>
                    <div class="tag-list">
                        {' '.join(f'<span class="tag topic">{html.escape(topic)}</span>' for topic in summary.topics)}
                    </div>
                </div>''' if summary.topics else ''}
                
                {f'''<div class="summary-card patterns">
                    <h3>Code Patterns</h3>
                    <div class="tag-list">
                        {' '.join(f'<span class="tag pattern">{html.escape(pattern)}</span>' for pattern in summary.code_patterns)}
                    </div>
                </div>''' if summary.code_patterns else ''}
            </div>
            
            {self._generate_debugging_info(summary.debugging_info) if summary.debugging_info else ''}
        </div>
        """
    
    def _generate_debugging_info(self, debugging_info: dict) -> str:
        """Generate debugging information section."""
        if not debugging_info:
            return ""
        
        items = []
        for key, value in debugging_info.items():
            items.append(f"""
                <div class="metadata-item">
                    <div class="metadata-label">{html.escape(key.title())}</div>
                    <div class="metadata-value">{html.escape(str(value))}</div>
                </div>
            """)
        
        return f"""
            <div style="margin-top: 25px;">
                <h3 style="margin-bottom: 15px; color: #e74c3c;">Debugging Information</h3>
                <div class="metadata">
                    {''.join(items)}
                </div>
            </div>
        """
    
    def _generate_conversation_section(self, conversation: ChatConversation) -> str:
        """Generate full conversation display section."""
        messages_html = []
        
        for i, message in enumerate(conversation.messages):
            timestamp_str = ""
            if message.timestamp:
                timestamp_str = message.timestamp.strftime('%I:%M %p')
            
            formatted_content = self._format_message_content(message.content)
            
            messages_html.append(f"""
                <div class="message {message.role}">
                    <div class="message-header">
                        <span class="role-badge {message.role}">{message.role}</span>
                        <span class="message-timestamp">{timestamp_str}</span>
                    </div>
                    <div class="message-content">
                        {formatted_content}
                    </div>
                    <div class="stats-bar">
                        <span>Message {i + 1} of {len(conversation.messages)}</span>
                        <span class="word-count">{message.word_count} words</span>
                    </div>
                </div>
            """)
        
        return f"""
        <div class="conversation-section">
            <div class="conversation-header">
                <h2>Full Conversation</h2>
            </div>
            {''.join(messages_html)}
        </div>
        """
    
    def _format_message_content(self, content: str) -> str:
        """Format message content with proper HTML rendering."""
        # Escape HTML first
        content = html.escape(content)
        
        # Convert markdown-style formatting
        content = self._convert_markdown_to_html(content)
        
        return content
    
    def _convert_markdown_to_html(self, content: str) -> str:
        """Convert basic markdown to HTML."""
        # Code blocks with syntax highlighting
        content = re.sub(
            r'```(\w+)?\n(.*?)\n```',
            lambda m: f'<pre><code class="language-{m.group(1) or "text"}">{m.group(2)}</code></pre>',
            content,
            flags=re.DOTALL
        )
        
        # Inline code
        content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
        
        # Headers
        content = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
        content = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
        content = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
        
        # Bold and italic
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
        
        # Lists
        content = re.sub(r'^- (.*?)$', r'<li>\1</li>', content, flags=re.MULTILINE)
        content = re.sub(r'(<li>.*?</li>\n?)+', r'<ul>\g<0></ul>', content, flags=re.DOTALL)
        
        # Links
        content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', content)
        
        # Paragraphs (split by double newlines)
        paragraphs = content.split('\n\n')
        paragraphs = [f'<p>{p.replace(chr(10), "<br>")}</p>' if p.strip() and not p.startswith('<') else p for p in paragraphs]
        content = '\n\n'.join(paragraphs)
        
        return content
    
    def _get_javascript(self) -> str:
        """Get JavaScript for interactive features."""
        return """
        // Scroll to top functionality
        const scrollTopBtn = document.createElement('button');
        scrollTopBtn.className = 'scroll-top';
        scrollTopBtn.innerHTML = '↑';
        scrollTopBtn.onclick = () => window.scrollTo({top: 0, behavior: 'smooth'});
        document.body.appendChild(scrollTopBtn);
        
        window.addEventListener('scroll', () => {
            if (window.pageYOffset > 300) {
                scrollTopBtn.classList.add('visible');
            } else {
                scrollTopBtn.classList.remove('visible');
            }
        });
        
        // Initialize Prism.js for syntax highlighting
        if (typeof Prism !== 'undefined') {
            Prism.highlightAll();
        }
        """


def generate_chat_html_report(conversation_input: Union[str, Path], 
                             output_path: Optional[Path] = None) -> Path:
    """Convenience function to generate HTML report.
    
    Args:
        conversation_input: Conversation ID, chat file path, or project path
        output_path: Where to save HTML file (auto-generated if None)
        
    Returns:
        Path to generated HTML file
    """
    reporter = ChatHtmlReporter()
    return reporter.generate_report(conversation_input, output_path)