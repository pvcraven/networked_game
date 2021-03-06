import arcade
import logging

from .layout_xml import process_svg
from .layout_xml import get_rect_info
from .layout_xml import get_point_info
from .layout_xml import get_shape_at
from .layout_xml import get_rect_for_name
from .layout_xml import Rect
from .layout_xml import Text
from .text_replacement import text_replacement
from .dimension_calculations import calculate_screen_data
from .lookup_image import lookup_image

logger = logging.getLogger(__name__)


class GameViewXML(arcade.View):
    """ Our custom Window Class"""

    def __init__(self):
        """ Initializer """
        # Call the parent class initializer
        super().__init__()
        logger.debug("GameViewXML.__init__")
        arcade.set_background_color(arcade.color.PAPAYA_WHIP)

        # Pieces
        self.piece_list = arcade.SpriteList()
        self.actions_list = arcade.SpriteList()

        # List of items we are dragging with the mouse
        self.held_items = []

        # Original location of cards we are dragging with the mouse in case
        # they have to go back.
        self.held_items_original_position = []

        self.svg = process_svg("networked_game/gui/layout.svg")

        self.process_game_data(self.window.game_data)

    def on_update(self, delta_time):

        # Service client network tasks
        self.window.communications_channel.service_channel()

        # Are we a server? If so, service that
        if self.window.server:
            self.window.server.server_check()

        # Any messages to process?
        if not self.window.communications_channel.receive_queue.empty():
            data = self.window.communications_channel.receive_queue.get()
            self.window.game_data = data
            self.process_game_data(data)

    def process_game_data(self, data):

        # Create new sprite lists
        self.piece_list = arcade.SpriteList()
        self.actions_list = arcade.SpriteList()

        origin_x, origin_y, ratio = calculate_screen_data(self.svg.width, self.svg.height,
                                                          self.window.width, self.window.height)
        logger.debug(f"{self.svg.width=}, {self.svg.height=}, {self.window.width=}, {self.window.height=}")
        logger.debug(f"{origin_x=}, {origin_y=}, {ratio=}")

        locations = {}

        def process_items(items, sprite_list):
            """ Create sprites and put them in the correct location"""

            # Loop through each item in the list we are given
            for item in items:
                logger.debug(f"Placing {item['name']}, {item['location']}")

                # Get the rect for this location from the SVG
                rect = get_rect_for_name(self.svg, item["location"])
                if not rect:
                    logger.warning(f"Can't find location named {item['location']} to place {item['name']}.")
                    continue

                # Get rect, adjusted for our screen dimensions
                cx, cy, width, height = get_rect_info(rect, origin_x, origin_y, ratio)

                # Figure out what image to use for this sprite
                image_name = lookup_image(item['name'])

                if not image_name:
                    logger.warning(f"Can't find image for {item['location']}, so can't create sprite.")
                    continue

                # Create sprite
                logger.debug(f"Drawing with image {image_name}")
                sprite = arcade.Sprite(image_name, ratio)
                sprite.properties['name'] = item['name']
                sprite.position = cx, cy
                sprite_list.append(sprite)
                logger.debug(f"Placed {item['name']} located at {item['location']} at ({cx}, {cy})")

                # What if there is another sprite at the same location? This will offset it
                if item['location'] in locations:
                    for other_sprite in locations[item['location']]:
                        other_sprite.center_x += 15
                    locations[item['location']].append(sprite)
                else:
                    locations[item['location']] = [sprite]

        # logger.debug(f"- Placements")
        # placement_list = data["placements"]
        # process_items(placement_list, self.piece_list)
        logger.debug(f"- Pieces")
        pieces_list = data["game_board"]["pieces"]
        process_items(pieces_list, self.piece_list)
        # logger.debug(f"- Actions")
        # pieces_list = data["action_items"]
        # process_items(pieces_list, self.actions_list)

    def draw_layout(self):

        origin_x, origin_y, ratio = calculate_screen_data(self.svg.width, self.svg.height,
                                                          self.window.width, self.window.height)
        for shape in self.svg.shapes:
            if isinstance(shape, Rect):

                cx, cy, width, height = get_rect_info(shape, origin_x, origin_y, ratio)
                if "fill" in shape.style:
                    color = shape.style["fill"]
                    if isinstance(color, str) and color.startswith("#"):
                        h = color.lstrip('#')
                        color = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
                        if "fill-opacity" in shape.style:
                            opacity = int(float(shape.style["fill-opacity"]) * 255)
                            color.append(opacity)
                        arcade.draw_rectangle_filled(cx, cy, width, height, color)
                if "stroke" in shape.style:
                    color = shape.style["stroke"]
                    if isinstance(color, str) and color.startswith("#"):
                        h = color.lstrip('#')
                        color = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
                        if "stroke-opacity" in shape.style:
                            opacity = int(float(shape.style["stroke-opacity"]) * 255)
                            color.append(opacity)

                        stroke_width = shape.style["stroke-width"] * ratio
                        arcade.draw_rectangle_outline(cx, cy, width, height, color, stroke_width)
            elif isinstance(shape, Text):
                x, y = get_point_info(shape.x, shape.y, origin_x, origin_y, ratio)
                text = text_replacement(shape.text, self.window.game_data)
                text_size_string = shape.style["font-size"]
                text_size_string = text_size_string[:-2]
                text_size_float = float(text_size_string) * 2.5 * ratio
                arcade.draw_text(text, x, y, arcade.color.BLACK, text_size_float)

    def on_draw(self):
        arcade.start_render()
        self.draw_layout()
        self.piece_list.draw()
        self.actions_list.draw()

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height)
        self.process_game_data(self.window.game_data)

    def on_mouse_press(self, x, y, button, key_modifiers):
        """ Called when the user presses a mouse button. """

        # Get list of cards we've clicked on
        pieces = arcade.get_sprites_at_point((x, y), self.piece_list)

        # Have we clicked on a card?
        if len(pieces) > 0:

            # Might be a stack, get the top one
            primary = pieces[-1]

            # All other cases, grab the face-up card we are clicking on
            self.held_items = [primary]
            # Save the position
            self.held_items_original_position = [self.held_items[0].position]

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        """ User moves mouse """

        # If we are holding items, move them with the mouse
        for item in self.held_items:
            item.center_x += dx
            item.center_y += dy

    def on_mouse_release(self, x: float, y: float, button: int,
                         modifiers: int):
        """ Called when the user presses a mouse button. """

        # If we don't have any cards, who cares
        if len(self.held_items) == 0:
            return

        origin_x, origin_y, ratio = calculate_screen_data(self.svg.width, self.svg.height,
                                                          self.window.width, self.window.height)
        destination = get_shape_at(self.svg, origin_x, origin_y, ratio, x, y)

        if destination:
            for item in self.held_items:
                item_name = item.properties['name']
                destination_name = destination.id
                logger.debug(f"Move {item_name} to {destination_name}")

                data = {"command": "move_piece",
                        "name": item_name,
                        "destination": destination_name}

                self.window.communications_channel.send_queue.put(data)
        else:
            logger.debug(f"No item at dropped location")

            for i, item in enumerate(self.held_items):
                item.position = self.held_items_original_position[i]

        self.held_items = []
