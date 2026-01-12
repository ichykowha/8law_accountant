class ErrorHandler:
    def __init__(self):
        # Requirements for specific tasks
        self.requirements = {
            "interest": ["principal", "rate", "time"],
            "tax": ["income"]
        }
        self.pending_task = None
        self.collected_data = {}

    def check_for_missing_data(self, task_type, current_data):
        """Identifies what information is missing to complete a task."""
        missing = []
        for req in self.requirements.get(task_type, []):
            if req not in current_data:
                missing.append(req)
        return missing

    def handle_invalid_input(self, value, expected_type):
        """Ensures the user didn't type 'abc' where a number should be."""
        try:
            # Strip whitespace and common currency symbols
            clean_value = str(value).replace('$', '').replace(',', '').strip()
            if expected_type == float:
                return float(clean_value)
            return value
        except ValueError:
            return None