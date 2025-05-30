import os
import re
import json
import logging
import time
import urllib.parse
from datetime import date, datetime
from typing import Set, List, Dict
from random import randint
from pathlib import Path
from github import Github
from github.Repository import Repository

from utils import IssuePackage, REQUEST_REPO, AUTO_ASSIGN_LABEL, AUTO_PARSE_LABEL, get_origin_link_and_tag,\
    MULTI_LINK_LABEL, INCONSISTENT_TAG, TYPESPEC_LABEL

_LOG = logging.getLogger(__name__)

# assignee dict which will be assigned to handle issues
_LANGUAGE_OWNER = {'msyyc'}

# 'github assignee': 'token'
_ASSIGNEE_TOKEN = os.getenv('AZURESDK_BOT_TOKEN')

_SWAGGER_URL = 'https://github.com/Azure/azure-rest-api-specs/blob/main/specification'
_SWAGGER_PULL = 'https://github.com/Azure/azure-rest-api-specs/pull'
_HINTS = ["FirstGA", "FirstBeta", "HoldOn", "OnTime", "ForCLI", TYPESPEC_LABEL]


class IssueProcess:
    """
    # won't be changed anymore after __init__
    owner = ''  # issue owner
    assignee_candidates = {}  # assignee candidates who will be assigned to handle issue
    language_owner = {}  # language owner who may handle issue

    # will be changed by order
    issue_package = None  # issue that needs to handle
    assignee = ''
    bot_advice = []  # bot advice to help SDK owner
    target_readme_tag = ''  # swagger content that customers want
    readme_link = ''  # https link which swagger definition is in
    default_readme_tag = ''  # configured in `README.md`
    package_name = ''  # target package name
    target_date = ''  # target release date asked by customer
    date_from_target = 0
    spec_repo = None  # local swagger repo path
    """

    def __init__(self, issue_package: IssuePackage, request_repo: Repository,
                 assignee_candidates: Set[str], language_owner: Set[str]):
        self.issue_package = issue_package
        self.assignee = issue_package.issue.assignee.login if issue_package.issue.assignee else ''
        self.owner = issue_package.issue.user.login
        self.created_time = issue_package.issue.created_at
        self.assignee_candidates = assignee_candidates
        self.language_owner = language_owner
        self.bot_advice = []
        self.target_readme_tag = ''
        self.readme_link = ''
        self.default_readme_tag = ''
        self.edit_content = ''
        self.package_name = ''
        self.target_date = ''
        self.date_from_target = 0
        self.is_open = True
        self.issue_title = issue_package.issue.title.split(": ", 1)[-1]
        self.full_issue_title = issue_package.issue.title
        self.spec_repo = Path(os.getenv('SPEC_REPO'))
        self.typespec_json = Path(os.getenv('TYPESPEC_JSON'))
        self.language_name = "common"
        self.request_repo = request_repo

    @property
    def for_typespec(self) -> bool:
        with open(str(self.typespec_json), "r") as file:
            data = json.load(file)
        return self.package_name in data.get(self.language_name, [])

    def has_label(self, label: str) -> bool:
        return label in self.issue_package.labels_name

    @property
    def created_date_format(self) -> str:
        return str(date.fromtimestamp(self.issue_package.issue.created_at.timestamp()).strftime('%m-%d'))

    @property
    def target_date_format(self) -> str:
        try:
            return str(datetime.strptime(self.target_date, "%Y-%m-%d").strftime('%m-%d'))
        except:
            return str(self.target_date)

    def get_issue_body(self) -> List[str]:
        return [i for i in self.issue_package.issue.body.split("\n") if i]

    def handle_link_contains_commit(self, link: str) -> str:
        if 'commit' in link:
            commit_sha = link.split('commit/')[-1]
            commit = self.issue_package.rest_repo.get_commit(commit_sha)
            link = commit.files[0].blob_url
            link = re.sub('blob/(.*?)/specification', 'blob/main/specification', link)
        return link

    def comment(self, message: str) -> None:
        self.issue_package.issue.create_comment(message)

    # get "workloads/resource-manager" from "workloads/resource-manager/Microsoft.Workloads/stable/2023-04-01/operations.json"
    def get_valid_relative_readme_folder(self, readme_folder: str) -> str:
        folder = Path(Path(readme_folder).as_posix().strip("/"))
        while "resource-manager" in str(folder):
            if Path(self.spec_repo, folder, "readme.md").exists():
                return folder.as_posix()
            folder = folder.parent

        return folder.as_posix()

    def get_readme_from_pr_link(self, link: str) -> str:
        pr_number = int(link.replace(f"{_SWAGGER_PULL}/", "").split('/')[0])

        # Get Readme link
        pr_info = self.issue_package.rest_repo.get_pull(number=pr_number)
        pk_url_name = set()
        for pr_changed_file in pr_info.get_files():
            contents_url = urllib.parse.unquote(pr_changed_file.contents_url)
            if '/resource-manager' not in contents_url:
                continue
            try:
                pk_url_name.add(self.get_valid_relative_readme_folder(contents_url.split('/specification')[1]))
            except Exception as e:
                continue
        readme_link = [f'{_SWAGGER_URL}/{item}' for item in pk_url_name]
        if len(readme_link) > 1:
            multi_link = ', '.join(readme_link)
            pr = f"{_SWAGGER_PULL}/{pr_number}"
            self.comment(
                f'Hi, @{self.assignee}, by parsing {pr}, there are multi service link: {multi_link}. Please decide which one is the right.')
            self.add_label(MULTI_LINK_LABEL)
            raise Exception(f'multi link in "{pr}"')

        return readme_link[0]

    def get_readme_link(self, origin_link: str):
        # check whether link is valid
        if 'azure-rest-api-specs' not in origin_link:
            self.comment(f'Hi, @{self.owner}, "{origin_link}" is not valid link. Please follow [doc]'
                         f'(https://github.com/Azure/azure-rest-api-specs/blob/main/documentation/release-request/'
                         f'rules-for-release-request.md#2-link-to-pr-or-spec-if-pr-unavailable) to provide valid link like '
                         f'"https://github.com/Azure/azure-rest-api-specs/pull/16750" or '
                         f'"https://github.com/Azure/azure-rest-api-specs/tree/main/'
                         f'specification/network/resource-manager"')
            raise Exception('Invalid link!')
        elif 'azure-rest-api-specs-pr' in origin_link:
            self.comment(f'Hi @{self.owner}, only [Azure/azure-rest-api-specs](https://github.com/Azure/'
                         f'azure-rest-api-specs) is permitted to publish SDK, [Azure/azure-rest-api-specs-pr]'
                         f'(https://github.com/Azure/azure-rest-api-specs-pr) is not permitted. '
                         f'Please paste valid link!')
            raise Exception('Invalid link from private repo')

        # change commit link to pull json link(i.e. https://github.com/Azure/azure-rest-api-specs/
        # commit/77f5d3b5d2#diff-708c2fb)
        link = self.handle_link_contains_commit(origin_link)

        # if link is a pr, it can get both pakeage name and readme link.
        if 'pull' in link:
            self.readme_link = self.get_readme_from_pr_link(link)
        # if link is a url(i.e. https://github.com/Azure/azure-rest-api-specs/blob/main/specification/
        # xxx/resource-manager/readme.md)
        elif '/resource-manager' not in link:
            # (i.e. https://github.com/Azure/azure-rest-api-specs/tree/main/specification/xxxx)
            self.readme_link = link + '/resource-manager'
        else:
            relative_readme_folder = self.get_valid_relative_readme_folder(link.split('/specification')[1])
            self.readme_link = f"{_SWAGGER_URL}/{relative_readme_folder}"

    @property
    def readme_local(self) -> str:
        return str(Path(self.spec_repo, self.readme_link.split('specification/')[1]))
    
    def local_file(self, name: str = "readme.md") -> Path:
        return Path(self.readme_local, name)

    def get_local_file_content(self, name: str = "readme.md") -> str:
        with open(Path(self.readme_local, name), 'r', encoding='utf-8') as f:
            return f.read()

    def get_default_readme_tag(self) -> None:
        contents = self.get_local_file_content()
        pattern_tag = re.compile(r'tag: package-[\w+-.]+')
        self.default_readme_tag = pattern_tag.search(contents).group().split(':')[-1].strip()

    def get_edit_content(self) -> None:
        self.edit_content = f'\n{self.readme_link.replace("/readme.md", "")}'

    def edit_issue_body(self) -> None:
        self.get_edit_content()
        issue_body_list = [i for i in self.issue_package.issue.body.split("\n") if i]
        issue_body_list.insert(0, self.edit_content)
        issue_body_up = ''
        # solve format problems
        for raw in issue_body_list:
            if raw == '---\r' or raw == '---':
                issue_body_up += '\n'
            issue_body_up += raw + '\n'
        self.issue_package.issue.edit(body=issue_body_up)

    def check_tag_consistency(self) -> None:
        self.target_readme_tag = self.target_readme_tag.replace('tag-', '')
        if self.default_readme_tag != self.target_readme_tag:
            self.add_label(INCONSISTENT_TAG)
            if "typespec" not in self.full_issue_title.lower():
                self.comment(f'Hi, @{self.owner}, according to [rule](https://github.com/Azure/azure-rest-api-specs/blob/'
                            f'main/documentation/release-request/rules-for-release-request.md#3-readme-tag-to-be-released),'
                            f' your **Readme Tag** is `{self.target_readme_tag}`, but in [readme.md]({self.readme_link}#basic-information) '
                            f'it is still `{self.default_readme_tag}`, please modify the readme.md or your '
                            f'**Readme Tag** above ')

    def get_package_name(self) -> None:
        issue_body_list = self.get_issue_body()
        for line in issue_body_list:
            if line.strip('\r\n ').startswith('package-name:'):
                self.package_name = line.split(':')[-1].strip('\r\n ')
                break

    def auto_parse(self) -> None:
        if self.has_label(AUTO_PARSE_LABEL):
            self.get_package_name()
            return

        self.add_label(AUTO_PARSE_LABEL)
        issue_body_list = self.get_issue_body()

        # Get the origin link and readme tag in issue body
        origin_link, target_readme_tag = get_origin_link_and_tag(issue_body_list)
        self.target_readme_tag = target_readme_tag if not self.target_readme_tag else self.target_readme_tag

        # get readme_link
        self.get_readme_link(origin_link)

        # get default tag with readme_link
        self.get_default_readme_tag()

        self.check_tag_consistency()

        self.edit_issue_body()

    def add_label(self, label: str) -> None:
        if not self.has_label(label):
            self.issue_package.issue.add_to_labels(label)
            self.issue_package.labels_name.add(label)

    def update_assignee(self, assignee_to_del: str, assignee_to_add: str) -> None:
        if assignee_to_del:
            self.issue_package.issue.remove_from_assignees(assignee_to_del)
        self.issue_package.issue.add_to_assignees(assignee_to_add)
        self.assignee = assignee_to_add

    def log(self, message: str) -> None:
        _LOG.info(f'issue {self.issue_package.issue.number}: {message}')

    def update_issue_instance(self) -> None:
        self.issue_package.issue = self.request_repo.get_issue(self.issue_package.issue.number)

    def auto_assign_policy(self) -> str:
        assignees = list(self.assignee_candidates)
        random_idx = randint(0, len(assignees) - 1) if len(assignees) > 1 else 0
        return assignees[random_idx]

    def auto_assign(self) -> None:
        if self.has_label(AUTO_ASSIGN_LABEL):
            self.update_issue_instance()
            return
        # assign averagely
        assignee = self.auto_assign_policy()

        # update assignee
        if self.assignee != assignee:
            self.log(f'remove assignee "{self.issue_package.issue.assignee}" and add "{assignee}"')
            self.assignee = assignee
            self.update_issue_instance()
            self.update_assignee(self.issue_package.issue.assignee, assignee)
        else:
            self.update_issue_instance()
        self.add_label(AUTO_ASSIGN_LABEL)

    def new_issue_policy(self):
        new_issue_advice = 'new issue.'
        if self.issue_package.issue.comments == 0:
            self.bot_advice.append(new_issue_advice)
        else:
            # issue that no comment from language owner will also be treated as new issue
            comment_from_owner = set(comment.user.login for comment in self.issue_package.issue.get_comments()
                                     if comment.user.login in self.language_owner)
            if not comment_from_owner:
                self.bot_advice.append(new_issue_advice)

    def new_comment_policy(self):
        if self.issue_package.issue.comments == 0:
            return
        comments = [(comment.updated_at.timestamp(), comment.user.login) for comment in
                    self.issue_package.issue.get_comments()]
        comments.sort()
        latest_comments = comments[-1][1]
        if latest_comments not in self.language_owner:
            self.bot_advice.append('new comment.')

    def multi_link_policy(self):
        if self.has_label(MULTI_LINK_LABEL):
            self.bot_advice.append('multi readme link!')

    def inconsistent_tag_policy(self):
        if self.has_label(INCONSISTENT_TAG):
            self.bot_advice.append('Attention to inconsistent tag.')

    def remind_logic(self) -> bool:
        return abs(self.date_from_target) <= 2

    def print_date_from_target_date(self) -> str:
        return str(self.date_from_target) if self.remind_logic() else ''

    def date_remind_policy(self):
        if self.remind_logic():
            self.bot_advice.append('close to release date.')

    def hint_policy(self):
        for item in _HINTS:
            if self.has_label(item):
                self.bot_advice.append(f"{item}.")

    def typespec_policy(self):
        if self.for_typespec:
            self.add_label(TYPESPEC_LABEL)

    def auto_bot_advice(self):
        self.new_issue_policy()
        self.typespec_policy()
        self.new_comment_policy()
        self.multi_link_policy()
        self.date_remind_policy()
        self.inconsistent_tag_policy()
        self.hint_policy()

    def get_target_date(self):
        body = self.get_issue_body()
        try:
            try:
                self.target_date = [re.compile(r"\d{4}-\d{1,2}-\d{1,2}").findall(l)[0] for l in body if 'Target release date' in l][0]
            except Exception:
                try:
                    self.target_date = [re.compile(r"\d{1,2}/\d{1,2}/\d{4}").findall(l)[0] for l in body if 'Target release date' in l][0]
                    self.target_date = datetime.strptime(self.target_date, "%m/%d/%Y").strftime('%Y-%m-%d')
                except Exception:
                    self.target_date = [re.compile(r"\d{1,2}/\d{1,2}/\d{4}").findall(l)[0] for l in body if 'Target release date' in l][0]
                    self.target_date = datetime.strptime(self.target_date, "%d/%m/%Y").strftime('%Y-%m-%d')

            self.date_from_target = int((time.mktime(time.strptime(self.target_date, '%Y-%m-%d')) - time.time()) / 3600 / 24)
        except Exception:
            self.target_date = 'fail to get.'
            self.date_from_target = 1000  # make a ridiculous data to remind failure when error happens

    def update_owner(self) -> None:
        issue_body = self.get_issue_body()
        for line in issue_body:
            if "Requested by" in line:
                self.owner = line.split('@')[-1].strip(', *\r\n')
                break

    def run(self) -> None:
        # common part(don't change the order)
        self.update_owner()
        self.auto_assign()  # necessary flow
        self.auto_parse()  # necessary flow
        self.get_target_date()
        self.auto_bot_advice()  # make sure this is the last step


class Common:
    """ The class defines some function for all languages to reference
    issues_package = None  # issues that need to handle
    request_repo  # request repo instance generated by token
    assignee_candidates = {}  # assignee candidates who will be assigned to handle issue
    language_owner = {}  # language owner who may handle issue
    result = []
    file_out_name = ''  # file that storages issue status
    """

    def __init__(self, issues_package: List[IssuePackage], language_owner: Set[str],
                 sdk_assignees: Set[str], assignee_token=_ASSIGNEE_TOKEN):
        self.issues_package = issues_package
        self.language_owner = language_owner | sdk_assignees
        self.assignee_candidates = sdk_assignees
        # arguments add to language.md
        self.file_out_name = 'common.md'
        self.target_release_date = ''
        self.date_from_target = ''
        self.package_name = ''
        self.result = []
        self.request_repo = Github(assignee_token).get_repo(REQUEST_REPO)
        self.issue_process_function = IssueProcess

    @staticmethod
    def for_test():
        return bool(os.getenv("TEST_ISSUE_NUMBER"))

    def log_error(self, message: str) -> None:
        _LOG.error(message)

    def output(self):
        with open(self.file_out_name, 'w') as file_out:
            file_out.write('| id | issue | author | package | assignee | bot advice | created date of issue | target release date | date from target |\n')
            file_out.write('| ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | :-----: |\n')
            for idx, item in enumerate(self.result):
                try:
                    if item.is_open:
                        item_status = Common.output_md(idx + 1, item)
                        file_out.write(item_status)
                except Exception as e:
                    self.log_error(f'Error happened during output result of handled issue {item.issue_package.issue.number}: {e}')

    @staticmethod
    def output_md(idx: int, item: IssueProcess):
        return '| {} | [#{}]({}) | {} | {} | {} | {} | {} | {} | {} |\n'.format(
            idx,
            item.issue_package.issue.html_url.split('/')[-1],
            item.issue_package.issue.html_url,
            item.owner,
            item.package_name,
            item.assignee,
            ' '.join(item.bot_advice),
            item.created_date_format,
            item.target_date_format,
            item.print_date_from_target_date()
        )

    def proc_issue(self):
        for item in self.issues_package:
            issue = self.issue_process_function(item, self.request_repo, self.assignee_candidates,
                                                self.language_owner)

            try:
                issue.run()
            except Exception as e:
                self.log_error(f'Error happened during handling issue {item.issue.number}: {e}')
            self.result.append(issue)

    def run(self):
        self.proc_issue()
        self.output()


def common_process(issues: List[IssuePackage]) -> Common:
    return Common(issues,  _LANGUAGE_OWNER, _LANGUAGE_OWNER)
