from typing import Optional, Any

import disnake
import lavalink
from disnake.ext import commands

from EnvVariables import DM_Channel


class Client(commands.Bot):
    def __init__(self, **options: Any):
        """
        Custom Client class for the Assistant.
        This Inherits from disnake's Bot class.
        """
        super().__init__(**options)
        self._lava_host: str = options.get('lava_host')
        self._lava_port: int = options.get('lava_port')
        self._lava_password: str = options.get('lava_password')
        self._lava_region: str = options.get('lava_region')
        self._lava_node_name: str = options.get('lava_node_name')
        self._lavalink: Optional[lavalink.Client] = None

    @property
    def lavalink(self):
        """
        Returns the Lavalink Client
        """
        if self._lavalink is None:
            self._lavalink = lavalink.Client(self.user.id)
            self._lavalink.add_node(self._lava_host, self._lava_port,
                                    self._lava_password, self._lava_region, self._lava_node_name)
        return self._lavalink

    async def log(self, content: Optional[str] = None, embed: Optional[disnake.Embed] = None) -> None:
        """
        Logs messages to a Text Channel
        """
        channel = self.get_channel(DM_Channel)
        if channel is not None:
            await channel.send(content=content, embed=embed)
