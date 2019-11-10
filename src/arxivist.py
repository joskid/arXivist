from typing import List, Any, Tuple, Dict, Union, Set
import enum as e
import sys
import psycopg2 as psy
from src import retrieve_pdf as rpdf, retrieve_biblio as rb, db_entries as dbe, retrieve_paper as rp

BAD_CHARS = (' ')


class UserOptions(e.Enum):
    SEARCH = 'search'
    SUGGEST = 'suggest'
    EXPLORE = 'explore'

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, type(self)):
            return self is other
        elif isinstance(other, str):
            return other == self.value
        return False

    @staticmethod
    def is_valid_response(response: str) -> bool:
        return any([response == search_response for search_response in UserOptions])


class UserSearchResponses(e.Enum):
    MORE = 'more'
    CONT = 'cont'
    VIEW = 'view'
    ADD = 'add'
    QUIT = 'quit'

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, type(self)):
            return self is other
        elif isinstance(other, str):
            return other == self.value
        return False

    @staticmethod
    def is_valid_response(response: str) -> bool:
        return any([response == search_response for search_response in UserSearchResponses])


class SaveQuery:

    def __init__(self):
        self.selected_ids: Set[int] = set()
        self.valid_ids_to_info: Dict[int, rp.SearchResult] = {}

    def add_valid_id(self, result_id: int, result: rp.SearchQuery) -> None:
        if result_id in self.valid_ids_to_info:
            raise ValueError(f'id {result_id} already added to list of valid ids')
        self.valid_ids_to_info[result_id] = result

    def get_result(self, result_id: int) -> rp.SearchResult:
        if self.is_valid_id(result_id):
            return self.valid_ids_to_info[result_id]
        raise ValueError(f'id {result_id} is not a valid id')

    def select_id(self, param: int) -> None:
        if not self.is_valid_id(param):
            raise ValueError(f'{param} not in list of valid ids')
        self.selected_ids.add(param)

    def is_valid_id(self, result_id: int) -> bool:
        return result_id in self.valid_ids_to_info

    def __str__(self):
        if self.selected_ids:
            return f"save query: {', '.join([str(entry) for entry in self.selected_ids])}"
        return 'nothing in save query'

    def submit(self) -> None:
        with psy.connect(dbname='arxiv') as conn:
            with conn.cursor() as cursor:
                for result_id in self.selected_ids:
                    result = self.get_result(result_id)
                    pdf_path = rpdf.fetch_and_save_pdf(result.pdf_link)
                    references = rb.retrieve_references(result)
                    dbe.insert_search_query(cursor, result, references, pdf_path)


def is_list_of_n_ints(to_parse: List[str], n: int = -1) -> List[int]:
    if not to_parse:
        return []
    elif n > -1 and len(to_parse) != n:  # -1 means variable length
        raise ValueError(f'given list {to_parse} must have only {n} entries')

    for idx, entry in enumerate(to_parse):
        to_parse[idx] = int(entry)
    return to_parse


def validate_user_result_response(response: List[str], save_query: SaveQuery) -> Tuple[UserSearchResponses,
                                                                                       Union[int, List[int]]]:
    if not response:
        raise ValueError(f"not provided a response, must be one of {','.join([str(_) for _ in UserSearchResponses])}")

    cmd, params = response[0], response[1:]
    if not UserSearchResponses.is_valid_response(cmd):
        raise ValueError(f"invalid response {cmd}, must be one of {','.join([str(_) for _ in UserSearchResponses])}")

    if cmd == UserSearchResponses.MORE:
        selected_id = is_list_of_n_ints(params, 1)[0]
        if not save_query.is_valid_id(selected_id):
            raise ValueError(f'selected id {selected_id} is not a valid id')
        return UserSearchResponses.MORE, selected_id
    elif cmd == UserSearchResponses.ADD:
        return UserSearchResponses.ADD, is_list_of_n_ints(params)
    elif cmd == UserSearchResponses.CONT:
        return UserSearchResponses.CONT, is_list_of_n_ints(params, 0)
    elif cmd == UserSearchResponses.QUIT:
        return UserSearchResponses.QUIT, is_list_of_n_ints(params, 0)
    else:
        return UserSearchResponses.VIEW, is_list_of_n_ints(params, 0)


def delete_last_line():
    sys.stdout.write('\x1b[1A')  # move cursor up one line
    sys.stdout.write('\x1b[2K')  # delete last line


def format_params(params: List[str]) -> List[str]:
    for idx, param in enumerate(params):
        for char in BAD_CHARS:
            param = param.replace(char, '')
        params[idx] = param
    return list(filter(lambda x: bool(x), params))


def parse_mode(mode: str) -> None:
    if mode == UserOptions.EXPLORE:
        pass
    elif mode == UserOptions.SEARCH:
        pass
    elif mode == UserOptions.SUGGEST:
        pass
    raise ValueError(f'{mode} is not a supported mode')


def main():
    while True:
        try:
            mode = input(f"available modes are {', '.join([str(_) for _ in UserOptions])}")
            parse_mode(mode)


            params = input('enter search params\n')
            params = format_params(params.split(' '))
            search_query = rp.SearchQuery.from_params(params)

            save_query = SaveQuery()
            for responses in search_query.retrieve_search_results():
                for result_id, response in responses:
                    title = response.title
                    save_query.add_valid_id(result_id, response)
                    print(result_id, title)

                print("\noptions:\n"
                      "- 'more id' to view more info\n"
                      "- 'cont' to view more results\n"
                      "- 'add ids' to add results to save query\n"
                      "- 'view' to view current save query\n"
                      "- 'quit' to terminate responses and submit save query")

                wait_on_user = True
                while wait_on_user:
                    results_response = input('waiting...\n')
                    results_response = [result for result in results_response.split(' ') if result]
                    cmd, params = validate_user_result_response(results_response, save_query)

                    if cmd == UserSearchResponses.MORE:
                        print(save_query.get_result(params))
                    elif cmd == UserSearchResponses.ADD:
                        for param in params:
                            save_query.select_id(param)
                    elif cmd == UserSearchResponses.CONT:
                        wait_on_user = False
                    elif cmd == UserSearchResponses.QUIT:
                        save_query.submit()
                        break
                    elif cmd == UserSearchResponses.VIEW:
                        print(save_query)

        except Exception as e:
            raise e


if __name__ == '__main__':
    main()