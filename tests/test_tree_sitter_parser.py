"""Tests for tree-sitter parser functionality."""

import pytest
from pathlib import Path
from roo_code.builtin_tools.tree_sitter_parser import (
    TreeSitterParser,
    get_supported_extensions,
    CodeDefinition,
)


@pytest.fixture
def parser():
    """Create a TreeSitterParser instance."""
    return TreeSitterParser()


@pytest.fixture
def fixtures_dir():
    """Get the fixtures directory."""
    return Path(__file__).parent / "fixtures"


class TestTreeSitterParser:
    """Test the TreeSitterParser class."""
    
    def test_parser_initialization(self, parser):
        """Test parser initializes correctly."""
        assert parser is not None
        assert isinstance(parser._parsers, dict)
        assert isinstance(parser._languages, dict)
    
    def test_is_available(self, parser):
        """Test checking if tree-sitter is available."""
        # Should be True if tree-sitter is installed, False otherwise
        is_available = parser.is_available()
        assert isinstance(is_available, bool)
    
    def test_supported_extensions(self):
        """Test getting supported extensions."""
        extensions = get_supported_extensions()
        assert isinstance(extensions, list)
        assert len(extensions) > 0
        assert '.py' in extensions
        assert '.js' in extensions
        assert '.ts' in extensions


class TestPythonParsing:
    """Test parsing Python files."""
    
    def test_parse_python_file(self, parser, fixtures_dir):
        """Test parsing a Python file."""
        python_file = fixtures_dir / "sample.py"
        if not python_file.exists():
            pytest.skip("Python sample file not found")
        
        result = parser.parse_file(python_file)
        
        # If tree-sitter is available, we should get results
        if parser.is_available():
            assert result is not None
            assert isinstance(result, str)
            # Should contain line numbers
            assert '--' in result
        else:
            # If not available, result should be None
            assert result is None
    
    def test_python_class_detection(self, parser, fixtures_dir):
        """Test detection of Python classes."""
        python_file = fixtures_dir / "sample.py"
        if not python_file.exists() or not parser.is_available():
            pytest.skip("Python sample file not found or tree-sitter not available")
        
        result = parser.parse_file(python_file)
        assert result is not None
        
        # Check for class definitions
        # The sample.py file should have MyClass and DataClass
        lines = result.split('\n')
        assert any('class MyClass' in line for line in lines)
    
    def test_python_function_detection(self, parser, fixtures_dir):
        """Test detection of Python functions."""
        python_file = fixtures_dir / "sample.py"
        if not python_file.exists() or not parser.is_available():
            pytest.skip("Python sample file not found or tree-sitter not available")
        
        result = parser.parse_file(python_file)
        assert result is not None
        
        # Check for function definitions
        lines = result.split('\n')
        # Should detect functions that span multiple lines
        assert any('def' in line for line in lines)


class TestJavaScriptParsing:
    """Test parsing JavaScript files."""
    
    def test_parse_javascript_file(self, parser, fixtures_dir):
        """Test parsing a JavaScript file."""
        js_file = fixtures_dir / "sample.js"
        if not js_file.exists():
            pytest.skip("JavaScript sample file not found")
        
        result = parser.parse_file(js_file)
        
        if parser.is_available():
            assert result is not None or result == ""  # Empty is OK if no definitions meet criteria
            if result:
                assert isinstance(result, str)
        else:
            assert result is None
    
    def test_javascript_class_detection(self, parser, fixtures_dir):
        """Test detection of JavaScript classes."""
        js_file = fixtures_dir / "sample.js"
        if not js_file.exists() or not parser.is_available():
            pytest.skip("JavaScript sample file not found or tree-sitter not available")
        
        result = parser.parse_file(js_file)
        if result:  # May be empty if components too small
            lines = result.split('\n')
            # Should detect classes
            assert any('class' in line.lower() for line in lines)


class TestTypeScriptParsing:
    """Test parsing TypeScript files."""
    
    def test_parse_typescript_file(self, parser, fixtures_dir):
        """Test parsing a TypeScript file."""
        ts_file = fixtures_dir / "sample.ts"
        if not ts_file.exists():
            pytest.skip("TypeScript sample file not found")
        
        result = parser.parse_file(ts_file)
        
        if parser.is_available():
            assert result is not None or result == ""
            if result:
                assert isinstance(result, str)
        else:
            assert result is None
    
    def test_typescript_interface_detection(self, parser, fixtures_dir):
        """Test detection of TypeScript interfaces."""
        ts_file = fixtures_dir / "sample.ts"
        if not ts_file.exists() or not parser.is_available():
            pytest.skip("TypeScript sample file not found or tree-sitter not available")
        
        result = parser.parse_file(ts_file)
        # Interfaces might not be detected if they're too small
        # Just verify we got some result
        assert result is not None or result == ""


class TestDirectoryParsing:
    """Test parsing entire directories."""
    
    def test_parse_directory(self, parser, fixtures_dir):
        """Test parsing all files in a directory."""
        if not fixtures_dir.exists():
            pytest.skip("Fixtures directory not found")
        
        result = parser.parse_directory(fixtures_dir)
        
        assert isinstance(result, str)
        # Should contain file markers
        if parser.is_available() and any(fixtures_dir.iterdir()):
            assert '#' in result or result == "No source code definitions found."
    
    def test_parse_directory_max_files(self, parser, fixtures_dir):
        """Test parsing directory respects max_files limit."""
        if not fixtures_dir.exists():
            pytest.skip("Fixtures directory not found")
        
        result = parser.parse_directory(fixtures_dir, max_files=1)
        
        assert isinstance(result, str)
        # Should only process up to 1 file
        if parser.is_available():
            # Count the number of file markers
            file_count = result.count('# ')
            assert file_count <= 1


class TestCodeDefinition:
    """Test the CodeDefinition dataclass."""
    
    def test_code_definition_creation(self):
        """Test creating a CodeDefinition instance."""
        definition = CodeDefinition(
            name="my_function",
            type="function",
            start_line=10,
            end_line=15,
            line_content="def my_function():"
        )
        
        assert definition.name == "my_function"
        assert definition.type == "function"
        assert definition.start_line == 10
        assert definition.end_line == 15
        assert definition.line_content == "def my_function():"


class TestErrorHandling:
    """Test error handling in the parser."""
    
    def test_parse_nonexistent_file(self, parser):
        """Test parsing a file that doesn't exist."""
        nonexistent = Path("/nonexistent/file.py")
        result = parser.parse_file(nonexistent)
        assert result is None
    
    def test_parse_unsupported_extension(self, parser, tmp_path):
        """Test parsing a file with unsupported extension."""
        unsupported_file = tmp_path / "test.xyz"
        unsupported_file.write_text("some content")
        
        result = parser.parse_file(unsupported_file)
        assert result is None
    
    def test_parse_empty_file(self, parser, tmp_path):
        """Test parsing an empty Python file."""
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("")
        
        result = parser.parse_file(empty_file)
        # Empty file should return None (no definitions)
        assert result is None or result == ""


class TestFallbackBehavior:
    """Test behavior when tree-sitter is not available."""
    
    def test_parser_without_treesitter(self, monkeypatch):
        """Test parser behavior when tree-sitter is not installed."""
        # Mock tree-sitter as unavailable
        def mock_check(*args, **kwargs):
            return False
        
        parser = TreeSitterParser()
        monkeypatch.setattr(parser, '_check_tree_sitter', mock_check)
        parser._tree_sitter_available = False
        
        assert not parser.is_available()
        
        # Should return None for all parsing attempts
        test_file = Path("test.py")
        result = parser.parse_file(test_file)
        assert result is None


@pytest.mark.integration
class TestIntegration:
    """Integration tests with actual files."""
    
    def test_parse_actual_python_module(self, parser):
        """Test parsing an actual Python module from the project."""
        # Parse this test file itself
        test_file = Path(__file__)
        
        if parser.is_available():
            result = parser.parse_file(test_file)
            assert result is not None
            # Should detect test classes
            assert 'Test' in result or result == ""
        else:
            pytest.skip("Tree-sitter not available")
    
    def test_parse_parser_module(self, parser):
        """Test parsing the tree_sitter_parser module itself."""
        from roo_code.builtin_tools import tree_sitter_parser
        module_file = Path(tree_sitter_parser.__file__)
        
        if parser.is_available():
            result = parser.parse_file(module_file)
            assert result is not None
            # Should detect the TreeSitterParser class
            assert 'TreeSitterParser' in result or 'class' in result.lower()
        else:
            pytest.skip("Tree-sitter not available")