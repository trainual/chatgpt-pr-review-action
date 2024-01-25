import html
import os

from github import Github
import openai
import requests

class GitHubChatGPTPullRequestReviewer:
    def __init__(self):
        self._config_gh()
        self._config_openai()

    def _config_gh(self):
        gh_api_url = "https://api.github.com"

        self.gh_pr_id = os.environ.get("INPUT_GITHUB_PR_ID")
        self.gh_token = os.environ.get("INPUT_GITHUB_TOKEN")
        self.gh_repo_name = os.getenv('GITHUB_REPOSITORY')

        self.gh_pr_url = (
            f"{gh_api_url}/repos/{self.gh_repo_name}/pulls/{self.gh_pr_id}"
        )
        self.gh_headers = {
            'Authorization': f"token {self.gh_token}",
            'Accept': 'application/vnd.github.v3.diff'
        }
        self.gh_api = Github(self.gh_token)

    def _get_arg(self, arg_name: str, default_value: str):
        arg_value = os.environ.get(arg_name, default_value)
        if not arg_value:
            return default_value    
        return arg_value

    def _config_openai(self):
        skip_text = '{ "violations": [] }'
        openai_model_default = "gpt-4-1106-preview"
        openai_temperature_default = 0.5
        openai_max_tokens_default = 2048
        openai_rules_json_array_default = """
            [{
              "rule": "Code should follow the SOLID design principles",
            }, {
              "rule": "All text, including code, should be free of obvious spelling errors.",
              "good": [
                "The quick brown fox jumps over the lazy dog.",
                "card_template",
                "receive",
                "shippingLabel"
              ],
              "bad": [
                "The quack brown fox jumps over the lazy dog.",
                "card_templat",
                "recieve",
                "shipingLabel",
                "shippingLable"
              ]
            }]
        """
        openai_prompt_footer = f"""

        Do not comment on any rules for which there are no violations...do not even mention that they do not apply, just return "{skip_text}".
        Similarly, if there are violations that are in the removed code, they do not need to be mentioned.
        """
        comment_title_default = 'ChatGPT Review'
        comment_note_default = 'NOTE: Generated using an ChatGPT...use program, so some comments here would not make sense.'

        openai_api_key = os.environ.get("INPUT_OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = openai_api_key
        self.openai_model = self._get_arg("INPUT_OPENAI_MODEL", openai_model_default)
        self.openai_temperature = self._get_arg("INPUT_OPENAI_TEMPERATURE", openai_temperature_default)
        self.openai_max_tokens = self._get_arg("INPUT_OPENAI_MAX_TOKENS", openai_max_tokens_default)
        self.openai_rules_json_array = self._get_arg("INPUT_OPENAI_RULES_JSON_ARRAY", openai_rules_json_array_default)
        self.openai_prompt_extras = self._get_arg("INPUT_OPENAI_PROMPT_EXTRAS", '')
        self.comment_title = self._get_arg("INPUT_COMMENT_TITLE", comment_title_default)
        self.comment_note = self._get_arg("INPUT_COMMENT_NOTE", comment_note_default)

        if self.openai_prompt_extras:
            self.openai_prompt_extras += '\n'

        rule_format = '{ "rule": "Rule description", "good": ["example 1", "example 2"], "bad": ["example 1", "example 2", "example 3"] }'
        openai_prompt = f"""
            You are a GitHub pull request reviewer. Your job is to perform code reviews and provide actionable feedback on a set of rules. You will be provided
            a diff file where a "+" indicates a new line and a "-" indicates a removed line. If there is no "+" or "-" at the start then the line is unchanged.
            If there are no violations for any rules, then you should return just "{skip_text}" so that a script can detect that there are no violations.
            If there are violations, then you should return a list of the violations in the following, human-readable format...
            - Recommendation 1
            - Recommendation 2
            - Recommendation 3
              

            {self.openai_prompt_extras}

            A list of rules are provided below and will have the following format...
            {rule_format}

            In this format, "rule" is a description of the rule, "good" is a list of examples that follow the rule, and "bad" is a list of examples that violate the rule.

            Here is the array of rules...
        """

        self.skip_text = skip_text
        self.openai_prompt_footer = openai_prompt_footer

        openai.api_key = openai_api_key

        prompt_parts = (
            f"{openai_prompt.strip()}",
            self.openai_rules_json_array.strip(),
            "",
            self.openai_prompt_footer.strip()
        )
        self.chatgpt_initial_instruction = '\n'.join(prompt_parts).strip()

    def get_pr_content(self):
        response = requests.request("GET", self.gh_pr_url, headers=self.gh_headers)
        if response.status_code != 200:
            raise Exception(response.text)
        return response.text

    def get_diff(self) -> dict:
        repo = self.gh_api.get_repo(self.gh_repo_name)
        pull_request = repo.get_pull(int(self.gh_pr_id))

        content = self.get_pr_content()

        if len(content) == 0:
            pull_request.create_issue_comment(f"PR does not contain any changes")
            return ""

        parsed_text = content.split("diff")

        files_diff = {}
        content = []
        file_name = ""

        for diff_text in parsed_text:
            if len(diff_text) == 0:
                continue

            if not diff_text.startswith(' --git a/'):
                content += [diff_text]
                continue

            if file_name and content:
                files_diff[file_name] = "\n".join(content)

            file_name = diff_text.split("b/")[1].splitlines()[0]
            content = [diff_text]

        if file_name and content:
            files_diff[file_name] = "\n".join(content)

        return files_diff



    def pr_review(self, pr_diff: dict):
        system_message = [
            {"role": "system", "content": self.chatgpt_initial_instruction},
        ]
        print("Prompt: ", self.chatgpt_initial_instruction)

        results = []

        for filename, diff in pr_diff.items():
            message_diff = f"file: ```{filename}```\ndiff: ```{diff}```"
            messages = [{"role": "user", "content": message_diff}]

            print(
                "Estimated number of tokens: ",
                len(self.chatgpt_initial_instruction + message_diff) / 4
            )
            print("Diff: ", message_diff)

            try:
                # create a chat completion
                chat_completion = openai.ChatCompletion.create(
                    model=self.openai_model,
                    temperature=float(self.openai_temperature),
                    max_tokens=int(self.openai_max_tokens or self.openai_max_tokens_default),
                    messages=system_message + messages
                )
                response = chat_completion.choices[0].message.content

                print("File: ", filename)
                print("Response: ", response)

                if self.skip_text in response:
                    continue
                else:
                    results.append(
                        f"### {filename}\n\n{chat_completion.choices[0].message.content}\n\n---"
                    )
            except Exception as e:
                results.append(
                    f"### {filename}\nChatGPT was not able to review the file."
                    f" Error: {html.escape(str(e))}"
                )

        return results

    def comment_review(self, review: list):
        repo = self.gh_api.get_repo(self.gh_repo_name)
        pull_request = repo.get_pull(int(self.gh_pr_id))
        comment_parts = [
            f"# {self.comment_title}\n",
            f"*{self.comment_note}*\n"
        ]

        if len(review) == 0:
            comment_parts.append("No violations found!")
        else:
            comment_parts += review

        comment = '\n'.join(comment_parts)
        pull_request.create_issue_comment(comment)

    def run(self):
        pr_diff = self.get_diff()
        review = self.pr_review(pr_diff)
        self.comment_review(review)


if __name__ == "__main__":
    reviewer = GitHubChatGPTPullRequestReviewer()
    reviewer.run()
