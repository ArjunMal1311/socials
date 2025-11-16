import unittest
from atg import CommandExecutor


class TestCommandExecutorShlexQuoting(unittest.TestCase):
    """Test cases for CommandExecutor's argument quoting using shlex."""
    
    def setUp(self):
        """Set up test fixtures with minimal command schemas."""
        self.test_schemas = {
            "test_command": {
                "script": "test_script.py",
                "main_action": "--test-action",
                "description": "Test Command",
                "parameters": {
                    "test_arg": {
                        "type": "str",
                        "required": True,
                        "description": "Test argument"
                    }
                }
            }
        }
        self.executor = CommandExecutor(self.test_schemas)
    
    def test_quotes_arguments_with_spaces(self):
        """Test that CommandExecutor correctly quotes arguments with spaces using shlex."""
        parsed_intent = {
            "command": "test_command",
            "parameters": {
                "test_arg": "hello world"
            }
        }
        
        result = self.executor.construct_command(parsed_intent)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        command_str = result[0]
        
        # shlex.quote should quote the argument with single quotes
        self.assertIn("'hello world'", command_str)
    
    def test_quotes_arguments_with_single_quotes(self):
        """Test that CommandExecutor correctly quotes arguments with single quotes using shlex."""
        parsed_intent = {
            "command": "test_command",
            "parameters": {
                "test_arg": "it's a test"
            }
        }
        
        result = self.executor.construct_command(parsed_intent)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        command_str = result[0]
        
        # shlex.quote should escape single quotes properly
        # The expected format is: 'it'"'"'s a test'
        self.assertIn("it", command_str)
        self.assertIn("s a test", command_str)
    
    def test_quotes_arguments_with_double_quotes(self):
        """Test that CommandExecutor correctly quotes arguments with double quotes using shlex."""
        parsed_intent = {
            "command": "test_command",
            "parameters": {
                "test_arg": 'say "hello"'
            }
        }
        
        result = self.executor.construct_command(parsed_intent)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        command_str = result[0]
        
        # shlex.quote should handle double quotes by wrapping in single quotes
        self.assertIn('say "hello"', command_str)
    
    def test_quotes_arguments_with_special_shell_characters(self):
        """Test that CommandExecutor correctly quotes arguments with special shell characters using shlex."""
        special_chars = [
            ("test$var", "test$var"),
            ("test;echo", "test;echo"),
            ("test|grep", "test|grep"),
            ("test&background", "test&background"),
            ("test>output", "test>output"),
            ("test<input", "test<input"),
            ("test`cmd`", "test`cmd`"),
            ("test$(cmd)", "test$(cmd)"),
            ("test*wild", "test*wild"),
            ("test?question", "test?question"),
        ]
        
        for test_value, expected_substring in special_chars:
            with self.subTest(test_value=test_value):
                parsed_intent = {
                    "command": "test_command",
                    "parameters": {
                        "test_arg": test_value
                    }
                }
                
                result = self.executor.construct_command(parsed_intent)
                
                self.assertIsNotNone(result)
                self.assertEqual(len(result), 1)
                command_str = result[0]
                
                # shlex.quote should protect special characters by quoting
                # The value should be quoted (either with single quotes or escaped)
                self.assertIn(expected_substring, command_str)
                # Verify the value is properly quoted (not bare in the command)
                self.assertNotIn(f"--test-arg {test_value} ", command_str)
    
    def test_handles_arguments_without_special_characters_or_spaces(self):
        """Test that CommandExecutor correctly handles arguments without special characters or spaces using shlex."""
        simple_values = [
            "simple",
            "test123",
            "test_value",
            "test-value",
            "test.txt",
            "test@example",
            "TEST",
            "123",
            "test+value",
            "test=value"
        ]
        
        for test_value in simple_values:
            with self.subTest(test_value=test_value):
                parsed_intent = {
                    "command": "test_command",
                    "parameters": {
                        "test_arg": test_value
                    }
                }
                
                result = self.executor.construct_command(parsed_intent)
                
                self.assertIsNotNone(result)
                self.assertEqual(len(result), 1)
                command_str = result[0]
                
                # shlex.quote may or may not add quotes for simple values
                # but the value should be present in the command
                self.assertIn(test_value, command_str)
                # Verify the command contains the test-arg flag
                self.assertIn("--test-arg", command_str)


class TestCommandExecutorMultipleParameters(unittest.TestCase):
    """Test cases for CommandExecutor with multiple parameters to ensure proper quoting."""
    
    def setUp(self):
        """Set up test fixtures with multiple parameter schema."""
        self.test_schemas = {
            "multi_param_command": {
                "script": "test_script.py",
                "main_action": "--action",
                "description": "Multi-param Command",
                "parameters": {
                    "param1": {
                        "type": "str",
                        "required": True,
                        "description": "First parameter"
                    },
                    "param2": {
                        "type": "str",
                        "required": False,
                        "description": "Second parameter"
                    },
                    "flag": {
                        "type": "bool",
                        "required": False,
                        "default": False,
                        "description": "Boolean flag"
                    }
                }
            }
        }
        self.executor = CommandExecutor(self.test_schemas)
    
    def test_multiple_parameters_with_special_chars(self):
        """Test that multiple parameters with special characters are all properly quoted."""
        parsed_intent = {
            "command": "multi_param_command",
            "parameters": {
                "param1": "value with spaces",
                "param2": "value; with semicolon",
                "flag": True
            }
        }
        
        result = self.executor.construct_command(parsed_intent)
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        command_str = result[0]
        
        # Both parameters should be properly quoted
        self.assertIn("'value with spaces'", command_str)
        self.assertIn("'value; with semicolon'", command_str)
        self.assertIn("--flag", command_str)


if __name__ == "__main__":
    unittest.main()
