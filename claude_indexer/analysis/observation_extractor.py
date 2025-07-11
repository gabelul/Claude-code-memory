"""Observation extraction utilities for semantic enrichment."""

from typing import List, Optional, Set, Dict, Any
import re
import ast
from pathlib import Path

try:
    import tree_sitter
    import jedi
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from ..indexer_logging import get_logger
logger = get_logger()


class ObservationExtractor:
    """Extract semantic observations from code elements."""
    
    def __init__(self, project_path: Optional[Path] = None):
        """Initialize with optional project path for context."""
        self.project_path = project_path
        self._jedi_project = None
        
        if project_path and TREE_SITTER_AVAILABLE:
            try:
                self._jedi_project = jedi.Project(str(project_path))
            except Exception as e:
                logger.debug(f"Failed to initialize Jedi project: {e}")
    
    def extract_function_observations(
        self, 
        node: 'tree_sitter.Node',
        source_code: str,
        jedi_script: Optional['jedi.Script'] = None
    ) -> List[str]:
        """Extract observations for function entities with Jedi enrichment."""
        observations = []
        
        try:
            # 1. Extract docstring (Tree-sitter + Jedi enrichment)
            docstring = self._extract_docstring(node, source_code)
            
            # Try to get enhanced docstring from Jedi if available
            if jedi_script and not docstring:
                jedi_docstring = self._get_jedi_docstring(node, jedi_script, source_code)
                if jedi_docstring:
                    docstring = jedi_docstring
            
            if docstring:
                # First sentence is primary purpose
                sentences = docstring.split('.')
                if sentences:
                    purpose = sentences[0].strip()
                    if purpose:
                        observations.append(f"Purpose: {purpose}")
                
                # Look for specific patterns in docstring
                patterns = self._extract_docstring_patterns(docstring)
                observations.extend(patterns)
            
            # 2. Extract type hints from Jedi if available
            if jedi_script:
                type_info = self._extract_jedi_type_info(node, jedi_script, source_code)
                observations.extend(type_info)
            
            # 3. Extract function calls (behavior)
            calls = self._extract_function_calls(node, source_code)
            if calls:
                # Limit to most important calls
                call_list = list(calls)[:5]
                observations.append(f"Calls: {', '.join(call_list)}")
            
            # 4. Extract exception handling
            exceptions = self._extract_exception_handling(node, source_code)
            if exceptions:
                observations.append(f"Handles: {', '.join(exceptions)}")
            
            # 5. Extract return patterns
            return_info = self._extract_return_patterns(node, source_code)
            if return_info:
                observations.append(f"Returns: {return_info}")
            
            # 6. Extract parameter patterns
            param_info = self._extract_parameter_patterns(node, source_code)
            if param_info:
                observations.append(f"Parameters: {param_info}")
            
            # 7. Extract decorators (behavior modifiers)
            decorators = self._extract_decorators(node, source_code)
            for decorator in decorators:
                observations.append(f"Decorator: {decorator}")
            
            # 8. Extract complexity indicators
            complexity = self._calculate_complexity(node, source_code)
            if complexity > 5:  # Only note if significantly complex
                observations.append(f"Complexity: {complexity} (high)")
            
        except Exception as e:
            logger.debug(f"Error extracting function observations: {e}")
        
        return observations
    
    def extract_class_observations(
        self,
        node: 'tree_sitter.Node',
        source_code: str,
        jedi_script: Optional['jedi.Script'] = None
    ) -> List[str]:
        """Extract observations for class entities."""
        observations = []
        
        try:
            # 1. Extract class docstring
            docstring = self._extract_docstring(node, source_code)
            if docstring:
                sentences = docstring.split('.')
                if sentences:
                    purpose = sentences[0].strip()
                    if purpose:
                        observations.append(f"Responsibility: {purpose}")
            
            # 2. Extract key methods
            methods = self._extract_class_methods(node, source_code)
            if methods:
                # Show most important methods
                method_list = list(methods)[:5]
                observations.append(f"Key methods: {', '.join(method_list)}")
            
            # 3. Extract inheritance patterns
            inheritance = self._extract_inheritance_info(node, source_code)
            if inheritance:
                observations.append(f"Inherits from: {', '.join(inheritance)}")
            
            # 4. Extract class-level patterns
            patterns = self._detect_design_patterns(node, source_code)
            observations.extend(patterns)
            
            # 5. Extract attributes/properties
            attributes = self._extract_class_attributes(node, source_code)
            if attributes:
                attr_list = list(attributes)[:3]
                observations.append(f"Attributes: {', '.join(attr_list)}")
            
        except Exception as e:
            logger.debug(f"Error extracting class observations: {e}")
        
        return observations
    
    def _extract_docstring(self, node: 'tree_sitter.Node', source_code: str) -> Optional[str]:
        """Extract docstring/JSDoc from function or class node with deep AST traversal."""
        
        # Detect language based on node type
        is_javascript = node.type in ['function_declaration', 'arrow_function', 'function_expression', 'method_definition']
        
        if is_javascript:
            return self._extract_jsdoc_comment(node, source_code)
        else:
            return self._extract_python_docstring(node, source_code)
    
    def _extract_python_docstring(self, node: 'tree_sitter.Node', source_code: str) -> Optional[str]:
        """Extract Python docstring from function or class node."""
        def find_first_string_literal(n, depth=0):
            """Recursively find the first string literal in function/class body."""
            if depth > 3:  # Prevent infinite recursion
                return None
                
            # Check if this node is a string literal
            if n.type == 'string':
                return n.text.decode('utf-8')
            
            # For function/class definitions, look in the body
            if n.type in ['function_definition', 'class_definition', 'function_declaration', 'method_definition']:
                for child in n.children:
                    # Python uses 'block', JavaScript uses 'statement_block'
                    if child.type in ['block', 'statement_block']:
                        # Look for first statement that's a string
                        for stmt in child.children:
                            if stmt.type == 'expression_statement':
                                result = find_first_string_literal(stmt, depth + 1)
                                if result:
                                    return result
            
            # For expression statements, check children
            elif n.type == 'expression_statement':
                for child in n.children:
                    if child.type == 'string':
                        return child.text.decode('utf-8')
            
            # General recursive search
            else:
                for child in n.children:
                    result = find_first_string_literal(child, depth + 1)
                    if result:
                        return result
            
            return None
        
        # Actually call the helper function (this was missing!)
        try:
            raw_docstring = find_first_string_literal(node)
            if not raw_docstring:
                return None
            
            # Enhanced docstring cleaning
            docstring = raw_docstring.strip()
            
            # Remove triple quotes
            if docstring.startswith('"""') and docstring.endswith('"""'):
                docstring = docstring[3:-3]
            elif docstring.startswith("'''") and docstring.endswith("'''"):
                docstring = docstring[3:-3]
            # Remove single quotes
            elif docstring.startswith('"') and docstring.endswith('"'):
                docstring = docstring[1:-1]
            elif docstring.startswith("'") and docstring.endswith("'"):
                docstring = docstring[1:-1]
            
            # Clean up whitespace and return
            return docstring.strip() if docstring.strip() else None
            
        except Exception as e:
            logger.debug(f"Error extracting docstring: {e}")
            return None
    
    def _extract_jsdoc_comment(self, node: 'tree_sitter.Node', source_code: str) -> Optional[str]:
        """Extract JSDoc comment from JavaScript function node."""
        try:
            # Get the source lines
            lines = source_code.split('\n')
            
            # Look for comment before the function
            func_start_line = node.start_point[0]
            
            # Search backwards for JSDoc comment (/** */)
            jsdoc_lines = []
            in_jsdoc = False
            
            for i in range(func_start_line - 1, max(0, func_start_line - 10), -1):
                line = lines[i].strip()
                
                if line.endswith('*/'):
                    in_jsdoc = True
                    # Remove the */ and add the line
                    clean_line = line[:-2].strip()
                    if clean_line.startswith('*'):
                        clean_line = clean_line[1:].strip()
                    if clean_line:
                        jsdoc_lines.insert(0, clean_line)
                elif in_jsdoc and (line.startswith('*') or line.startswith('/**')):
                    # Remove the * or /** and add the line
                    clean_line = line.lstrip('/*').strip()
                    if clean_line.startswith('*'):
                        clean_line = clean_line[1:].strip()
                    if clean_line:
                        jsdoc_lines.insert(0, clean_line)
                elif in_jsdoc and line.startswith('/**'):
                    # Found the start of JSDoc
                    break
                elif in_jsdoc:
                    # End of JSDoc block
                    break
                elif line and not line.startswith('//'):
                    # Hit non-comment code, stop searching
                    break
            
            if jsdoc_lines:
                return ' '.join(jsdoc_lines)
            
            return None
        except Exception as e:
            logger.debug(f"Error extracting JSDoc comment: {e}")
            return None
    
    def _extract_docstring_patterns(self, docstring: str) -> List[str]:
        """Extract meaningful patterns and content from docstring."""
        patterns = []
        
        # Extract parameter information with details
        param_match = re.search(r'Args?:\s*(.*?)(?=\n\s*\n|\n\s*Returns?:|\n\s*Raises?:|\Z)', docstring, re.DOTALL | re.IGNORECASE)
        if param_match:
            param_text = param_match.group(1).strip()
            if param_text:
                # Extract parameter names
                param_names = re.findall(r'(\w+):\s*', param_text)
                if param_names:
                    patterns.append(f"Parameters: {', '.join(param_names[:3])}")
                else:
                    patterns.append("Has parameter documentation")
        
        # Extract return information with details
        return_match = re.search(r'Returns?:\s*(.*?)(?=\n\s*\n|\n\s*Raises?:|\n\s*Args?:|\Z)', docstring, re.DOTALL | re.IGNORECASE)
        if return_match:
            return_text = return_match.group(1).strip()
            if return_text:
                # Extract return type or description
                return_desc = return_text.split('\n')[0].strip()
                if len(return_desc) > 0:
                    patterns.append(f"Returns: {return_desc[:50]}{'...' if len(return_desc) > 50 else ''}")
                else:
                    patterns.append("Has return documentation")
        
        # Extract exception information with details
        raises_match = re.search(r'Raises?:\s*(.*?)(?=\n\s*\n|\n\s*Returns?:|\n\s*Args?:|\Z)', docstring, re.DOTALL | re.IGNORECASE)
        if raises_match:
            raises_text = raises_match.group(1).strip()
            if raises_text:
                # Extract exception types
                exception_types = re.findall(r'(\w+(?:Error|Exception)):', raises_text)
                if exception_types:
                    patterns.append(f"Raises: {', '.join(exception_types[:3])}")
                else:
                    patterns.append("Documents exceptions")
        
        # Look for Examples section
        if re.search(r'Examples?:', docstring, re.IGNORECASE):
            patterns.append("Has usage examples")
        
        # Extract behavioral keywords
        behavior_keywords = re.findall(r'\b(validates?|authenticates?|processes?|handles?|manages?|creates?|deletes?|updates?|retrieves?|calculates?|generates?|transforms?|parses?|formats?)\b', docstring.lower())
        if behavior_keywords:
            unique_behaviors = list(set(behavior_keywords))[:3]
            patterns.append(f"Behaviors: {', '.join(unique_behaviors)}")
        
        return patterns
    
    def _extract_function_calls(self, node: 'tree_sitter.Node', source_code: str) -> Set[str]:
        """Extract meaningful function calls using AST structural heuristics."""
        calls = set()
        
        def find_calls(n):
            if n.type == 'call':
                func_node = n.child_by_field_name('function')
                if func_node:
                    func_text = func_node.text.decode('utf-8')
                    
                    # Handle method calls (obj.method)
                    if '.' in func_text:
                        parts = func_text.split('.')
                        if len(parts) >= 2:
                            obj, method = parts[-2], parts[-1]
                            # Include meaningful obj.method patterns
                            if self._is_meaningful_by_structure(method):
                                calls.add(f"{obj}.{method}" if len(obj) < 10 else method)
                        func_name = parts[-1]
                    else:
                        func_name = func_text
                    
                    # Use existing builtin filter + structural heuristics
                    if not self._is_builtin_or_common(func_name) and self._is_meaningful_by_structure(func_name):
                        calls.add(func_name)
            
            for child in n.children:
                find_calls(child)
        
        find_calls(node)
        return calls
    
    def _is_meaningful_by_structure(self, func_name: str) -> bool:
        """Determine meaningfulness using AST structural heuristics."""
        # Snake_case indicates intentional naming
        if '_' in func_name:
            return True
        
        # Length > 4 indicates descriptive function
        if len(func_name) > 4:
            return True
        
        # CamelCase indicates class/constructor patterns
        if func_name[0].isupper() and any(c.isupper() for c in func_name[1:]):
            return True
        
        # Short names are usually noise
        return False
    
    def _extract_exception_handling(self, node: 'tree_sitter.Node', source_code: str) -> Set[str]:
        """Extract exception types that are caught with enhanced pattern recognition."""
        exceptions = set()
        
        def find_exceptions(n):
            if n.type == 'except_clause':
                # Enhanced exception type extraction
                for child in n.children:
                    # Single exception type
                    if child.type == 'identifier':
                        exc_name = child.text.decode('utf-8')
                        if exc_name not in ['as', 'except', 'e', 'err', 'error', 'ex']:
                            exceptions.add(exc_name)
                    
                    # Multiple exception types in tuple
                    elif child.type == 'tuple':
                        for tuple_child in child.children:
                            if tuple_child.type == 'identifier':
                                exc_name = tuple_child.text.decode('utf-8')
                                if exc_name not in ['as', 'except']:
                                    exceptions.add(exc_name)
                    
                    # Attribute access (e.g., module.Exception)
                    elif child.type == 'attribute':
                        attr_text = child.text.decode('utf-8')
                        if '.' in attr_text and 'Error' in attr_text or 'Exception' in attr_text:
                            exceptions.add(attr_text.split('.')[-1])
            
            # Also look for raised exceptions
            elif n.type == 'raise_statement':
                for child in n.children:
                    if child.type == 'call':
                        # Extract exception being raised
                        func_node = child.child_by_field_name('function')
                        if func_node and func_node.type == 'identifier':
                            exc_name = func_node.text.decode('utf-8')
                            if 'Error' in exc_name or 'Exception' in exc_name:
                                exceptions.add(exc_name)
                    elif child.type == 'identifier':
                        exc_name = child.text.decode('utf-8')
                        if 'Error' in exc_name or 'Exception' in exc_name:
                            exceptions.add(exc_name)
            
            for child in n.children:
                find_exceptions(child)
        
        find_exceptions(node)
        return exceptions
    
    def _extract_return_patterns(self, node: 'tree_sitter.Node', source_code: str) -> Optional[str]:
        """Extract return patterns from function."""
        returns = set()
        
        def find_returns(n):
            if n.type == 'return_statement':
                # Get the return value
                for child in n.children:
                    if child.type not in ['return', 'NEWLINE']:
                        return_text = child.text.decode('utf-8')
                        if return_text:
                            returns.add(return_text)
            
            for child in n.children:
                find_returns(child)
        
        find_returns(node)
        
        if returns:
            # Analyze return patterns
            return_list = list(returns)
            if len(return_list) == 1:
                return f"single value ({return_list[0][:20]}{'...' if len(return_list[0]) > 20 else ''})"
            elif len(return_list) > 1:
                return f"multiple patterns ({len(return_list)} different)"
            
        return None
    
    def _extract_parameter_patterns(self, node: 'tree_sitter.Node', source_code: str) -> Optional[str]:
        """Extract parameter patterns from function signature with parameter names."""
        try:
            # Look for parameters node
            for child in node.children:
                if child.type == 'parameters':
                    param_names = []
                    for param_child in child.children:
                        if param_child.type == 'identifier':
                            param_name = param_child.text.decode('utf-8')
                            param_names.append(param_name)
                        elif param_child.type == 'formal_parameter':
                            # For more complex parameter types
                            for identifier in param_child.children:
                                if identifier.type == 'identifier':
                                    param_name = identifier.text.decode('utf-8')
                                    param_names.append(param_name)
                                    break
                    
                    if param_names:
                        if len(param_names) <= 3:
                            return f"({', '.join(param_names)})"
                        else:
                            return f"({', '.join(param_names[:3])}, ...{len(param_names) - 3} more)"
            return None
        except Exception:
            return None
    
    def _extract_decorators(self, node: 'tree_sitter.Node', source_code: str) -> List[str]:
        """Extract decorators from function or class."""
        decorators = []
        
        try:
            # Look for decorator nodes before the function/class
            for child in node.children:
                if child.type == 'decorator':
                    decorator_text = child.text.decode('utf-8')
                    # Clean up the decorator
                    decorator_text = decorator_text.strip('@')
                    decorators.append(decorator_text)
        except Exception:
            pass
        
        return decorators
    
    def _extract_class_methods(self, node: 'tree_sitter.Node', source_code: str) -> Set[str]:
        """Extract method names from class body."""
        methods = set()
        
        def find_methods(n):
            if n.type == 'function_definition':
                # Get method name
                for child in n.children:
                    if child.type == 'identifier':
                        method_name = child.text.decode('utf-8')
                        # Skip dunder methods except __init__
                        if not method_name.startswith('__') or method_name == '__init__':
                            methods.add(method_name)
                        break
            
            for child in n.children:
                find_methods(child)
        
        find_methods(node)
        return methods
    
    def _extract_inheritance_info(self, node: 'tree_sitter.Node', source_code: str) -> List[str]:
        """Extract inheritance information from class definition."""
        inheritance = []
        
        try:
            # Look for argument_list (contains parent classes)
            for child in node.children:
                if child.type == 'argument_list':
                    for arg in child.children:
                        if arg.type == 'identifier':
                            parent_name = arg.text.decode('utf-8')
                            inheritance.append(parent_name)
                        elif arg.type == 'attribute':
                            # Handle module.Class inheritance
                            parent_name = arg.text.decode('utf-8')
                            inheritance.append(parent_name)
        except Exception:
            pass
        
        return inheritance
    
    def _detect_design_patterns(self, node: 'tree_sitter.Node', source_code: str) -> List[str]:
        """Detect design patterns in class."""
        patterns = []
        
        try:
            # Look for singleton pattern
            methods = self._extract_class_methods(node, source_code)
            if '__new__' in methods:
                patterns.append("Singleton pattern")
            
            # Look for factory pattern
            method_names = [m for m in methods if 'create' in m.lower() or 'build' in m.lower()]
            if method_names:
                patterns.append("Factory pattern")
            
            # Look for observer pattern
            if any('notify' in m.lower() or 'observe' in m.lower() for m in methods):
                patterns.append("Observer pattern")
            
        except Exception:
            pass
        
        return patterns
    
    def _extract_class_attributes(self, node: 'tree_sitter.Node', source_code: str) -> Set[str]:
        """Extract class attributes."""
        attributes = set()
        
        def find_attributes(n):
            if n.type == 'assignment':
                # Look for self.attribute assignments
                for child in n.children:
                    if child.type == 'attribute':
                        attr_text = child.text.decode('utf-8')
                        if attr_text.startswith('self.'):
                            attr_name = attr_text.split('.', 1)[1]
                            attributes.add(attr_name)
            
            for child in n.children:
                find_attributes(child)
        
        find_attributes(node)
        return attributes
    
    def _calculate_complexity(self, node: 'tree_sitter.Node', source_code: str) -> int:
        """Calculate complexity based on control flow statements."""
        complexity = 1  # Base complexity
        
        def count_complexity(n):
            nonlocal complexity
            if n.type in ['if_statement', 'elif_clause', 'for_statement', 'while_statement', 
                         'try_statement', 'except_clause', 'with_statement']:
                complexity += 1
            
            for child in n.children:
                count_complexity(child)
        
        count_complexity(node)
        return complexity
    
    def _is_builtin_or_common(self, func_name: str) -> bool:
        """Check if function name is a built-in or common library function."""
        builtins = {
            'print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple',
            'range', 'enumerate', 'zip', 'map', 'filter', 'sum', 'min', 'max', 'abs',
            'isinstance', 'hasattr', 'getattr', 'setattr', 'delattr', 'type', 'super',
            'open', 'input', 'format', 'join', 'split', 'strip', 'replace', 'find',
            'append', 'extend', 'insert', 'remove', 'pop', 'get', 'keys', 'values',
            'items', 'update', 'clear', 'copy', 'sort', 'reverse', 'count', 'index'
        }
        
        return func_name in builtins or len(func_name) <= 2
    
    def _get_jedi_docstring(self, node: 'tree_sitter.Node', jedi_script: 'jedi.Script', source_code: str) -> Optional[str]:
        """Get enhanced docstring from Jedi analysis."""
        try:
            # Get function name from Tree-sitter node
            func_name = None
            for child in node.children:
                if child.type == 'identifier':
                    func_name = child.text.decode('utf-8')
                    break
            
            if not func_name:
                return None
            
            # Get line number from node
            line_no = node.start_point[0] + 1
            
            # Try to get definition from Jedi
            definitions = jedi_script.goto(line_no, 0, follow_imports=True)
            for definition in definitions:
                if definition.name == func_name and hasattr(definition, 'docstring'):
                    docstring = definition.docstring()
                    if docstring and docstring.strip():
                        return docstring.strip()
            
            return None
        except Exception as e:
            logger.debug(f"Error getting Jedi docstring: {e}")
            return None
    
    def _extract_jedi_type_info(self, node: 'tree_sitter.Node', jedi_script: 'jedi.Script', source_code: str) -> List[str]:
        """Extract type information from Jedi analysis."""
        type_observations = []
        
        try:
            # Get function name from Tree-sitter node
            func_name = None
            for child in node.children:
                if child.type == 'identifier':
                    func_name = child.text.decode('utf-8')
                    break
            
            if not func_name:
                return type_observations
            
            # Get line number from node
            line_no = node.start_point[0] + 1
            
            # Try to get definition from Jedi
            definitions = jedi_script.goto(line_no, 0, follow_imports=True)
            for definition in definitions:
                if definition.name == func_name:
                    # Get return type if available
                    try:
                        if hasattr(definition, 'get_signatures'):
                            signatures = definition.get_signatures()
                            for sig in signatures:
                                if hasattr(sig, 'to_string'):
                                    sig_str = sig.to_string()
                                    if '->' in sig_str:
                                        return_type = sig_str.split('->')[-1].strip()
                                        if return_type and return_type != 'None':
                                            type_observations.append(f"Returns type: {return_type}")
                                
                                # Get parameter types
                                if hasattr(sig, 'params'):
                                    typed_params = []
                                    for param in sig.params:
                                        if hasattr(param, 'to_string'):
                                            param_str = param.to_string()
                                            if ':' in param_str:
                                                typed_params.append(param_str)
                                    
                                    if typed_params:
                                        type_observations.append(f"Typed parameters: {', '.join(typed_params[:3])}")
                    except Exception as e:
                        logger.debug(f"Error extracting Jedi signatures: {e}")
                    
                    break
            
        except Exception as e:
            logger.debug(f"Error extracting Jedi type info: {e}")
        
        return type_observations