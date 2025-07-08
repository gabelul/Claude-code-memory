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
        """Extract observations for function entities."""
        observations = []
        
        try:
            # 1. Extract docstring
            docstring = self._extract_docstring(node, source_code)
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
            
            # 2. Extract function calls (behavior)
            calls = self._extract_function_calls(node, source_code)
            if calls:
                # Limit to most important calls
                call_list = list(calls)[:5]
                observations.append(f"Calls: {', '.join(call_list)}")
            
            # 3. Extract exception handling
            exceptions = self._extract_exception_handling(node, source_code)
            if exceptions:
                observations.append(f"Handles: {', '.join(exceptions)}")
            
            # 4. Extract return patterns
            return_info = self._extract_return_patterns(node, source_code)
            if return_info:
                observations.append(f"Returns: {return_info}")
            
            # 5. Extract parameter patterns
            param_info = self._extract_parameter_patterns(node, source_code)
            if param_info:
                observations.append(f"Parameters: {param_info}")
            
            # 6. Extract decorators (behavior modifiers)
            decorators = self._extract_decorators(node, source_code)
            for decorator in decorators:
                observations.append(f"Decorator: {decorator}")
            
            # 7. Extract complexity indicators
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
        """Extract docstring from function or class node."""
        try:
            # Look for the first string literal in the body
            for child in node.children:
                if child.type == 'block':
                    for stmt in child.children:
                        if stmt.type == 'expression_statement':
                            for expr in stmt.children:
                                if expr.type == 'string':
                                    docstring = expr.text.decode('utf-8')
                                    # Clean up the docstring
                                    docstring = docstring.strip('\'"')
                                    if docstring.startswith('"""') or docstring.startswith("'''"):
                                        docstring = docstring[3:-3]
                                    elif docstring.startswith('"') or docstring.startswith("'"):
                                        docstring = docstring[1:-1]
                                    return docstring.strip()
            return None
        except Exception:
            return None
    
    def _extract_docstring_patterns(self, docstring: str) -> List[str]:
        """Extract meaningful patterns from docstring."""
        patterns = []
        
        # Look for Args/Parameters section
        if 'Args:' in docstring or 'Parameters:' in docstring:
            patterns.append("Has parameter documentation")
        
        # Look for Returns section
        if 'Returns:' in docstring or 'Return:' in docstring:
            patterns.append("Has return documentation")
        
        # Look for Raises section
        if 'Raises:' in docstring or 'Raises' in docstring:
            patterns.append("Documents exceptions")
        
        # Look for Examples section
        if 'Example:' in docstring or 'Examples:' in docstring:
            patterns.append("Has usage examples")
        
        return patterns
    
    def _extract_function_calls(self, node: 'tree_sitter.Node', source_code: str) -> Set[str]:
        """Extract function calls within a function body."""
        calls = set()
        
        def find_calls(n):
            if n.type == 'call':
                # Get the function name
                func_node = n.child_by_field_name('function')
                if func_node:
                    func_name = func_node.text.decode('utf-8')
                    # Extract just the function name (not module.function)
                    if '.' in func_name:
                        func_name = func_name.split('.')[-1]
                    # Filter out built-ins and common patterns
                    if not self._is_builtin_or_common(func_name):
                        calls.add(func_name)
            
            for child in n.children:
                find_calls(child)
        
        find_calls(node)
        return calls
    
    def _extract_exception_handling(self, node: 'tree_sitter.Node', source_code: str) -> Set[str]:
        """Extract exception types that are caught."""
        exceptions = set()
        
        def find_exceptions(n):
            if n.type == 'except_clause':
                # Look for exception type
                for child in n.children:
                    if child.type == 'identifier':
                        exc_name = child.text.decode('utf-8')
                        if exc_name not in ['as', 'except']:
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
        """Extract parameter patterns from function signature."""
        try:
            # Look for parameters node
            for child in node.children:
                if child.type == 'parameters':
                    param_count = len([c for c in child.children if c.type == 'identifier'])
                    if param_count > 0:
                        return f"{param_count} parameters"
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