??? Hint "Example Usage:"
    ```python
        from Interfluxer import check, has_any_role, slash_command

        @slash_command(name='cmd')
        @check(has_any_role(174918559539920897, 970018521511768094))
        async def some_command(ctx):
            ...


    ```
::: Interfluxer.models.internal.checks
